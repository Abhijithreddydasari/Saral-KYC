"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { CheckCircle2, Coffee, FileCheck2, Loader2, Sparkles } from "lucide-react";

import { AppShell } from "@/components/layout/app-shell";
import { useAuth } from "@/components/providers/auth-provider";
import { DocumentUploadWizard } from "@/components/applications/document-upload-wizard";
import { StatusIndicator } from "@/components/kyc/status-indicator";
import { StepWizard } from "@/components/wizard/step-wizard";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { apiClient } from "@/lib/api-client";
import { cn } from "@/lib/utils";
import type { ApplicationRead, DocumentRead } from "@/types/kyc";

type StepId = "basic" | "documents" | "liveness" | "success";

const steps = [
  { id: "basic", title: "Basic information", description: "Who are you + contact details" },
  { id: "documents", title: "Upload documents", description: "One at a time, max five" },
  { id: "liveness", title: "Liveliness check", description: "Selfie for MiniFASNet" },
  { id: "success", title: "Success", description: "Sit back & relax" },
];

interface BasicFormState {
  full_name: string;
  parent_name: string;
  contact_number: string;
  email: string;
  nationality: string;
  address_line: string;
  pincode: string;
}

const defaultFormState: BasicFormState = {
  full_name: "",
  parent_name: "",
  contact_number: "",
  email: "",
  nationality: "",
  address_line: "",
  pincode: "",
};

export default function CreateKycPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [currentStep, setCurrentStep] = useState<StepId>("basic");
  const [application, setApplication] = useState<ApplicationRead | null>(null);
  const [documents, setDocuments] = useState<DocumentRead[]>([]);
  const [selfieDoc, setSelfieDoc] = useState<DocumentRead | null>(null);
  const [formState, setFormState] = useState<BasicFormState>(defaultFormState);
  const [formError, setFormError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [selfieUploading, setSelfieUploading] = useState(false);
  const [selfieError, setSelfieError] = useState<string | null>(null);
  const [completionError, setCompletionError] = useState<string | null>(null);
  const [completing, setCompleting] = useState(false);

  useEffect(() => {
    if (!authLoading && !user) {
      router.replace("/login");
    }
  }, [authLoading, router, user]);

  useEffect(() => {
    if (!user) return;
    setFormState((prev) => ({
      ...prev,
      full_name: prev.full_name || user.full_name,
      email: prev.email || user.email || "",
    }));
    const loadExisting = async () => {
      try {
        const { data } = await apiClient.get<ApplicationRead[]>("/kyc/applications/mine");
        if (data.length) {
          const existing = data[0];
          setApplication(existing);
          setDocuments(existing.documents ?? []);
          const selfie = existing.documents?.find((doc) => doc.doc_type === "selfie") ?? null;
          setSelfieDoc(selfie);
          setFormState((prev) => ({
            ...prev,
            full_name: existing.full_name,
            parent_name: existing.parent_name ?? "",
            contact_number: existing.contact_number ?? "",
            email: existing.email ?? "",
            nationality: existing.nationality ?? "",
            address_line: existing.address_line ?? "",
            pincode: existing.pincode ?? "",
          }));

          if (existing.completed_at) {
            setCurrentStep("success");
          } else if (selfie) {
            setCurrentStep("liveness");
          } else if ((existing.documents?.filter((doc) => doc.doc_type !== "selfie").length ?? 0) > 0) {
            setCurrentStep("documents");
          }
        }
      } catch (error) {
        console.error("Failed to load existing application", error);
      } finally {
        setLoading(false);
      }
    };

    loadExisting();
  }, [user]);

  const documentLimitReached = useMemo(() => documents.filter((doc) => doc.doc_type !== "selfie").length >= 5, [documents]);

  const handleFormSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitting(true);
    setFormError(null);
    try {
      const payload = {
        ...formState,
        phone_number: formState.contact_number,
        preferred_language: "en",
      };
      const { data } = await apiClient.post<ApplicationRead>("/kyc/applications", payload);
      setApplication(data);
      setDocuments([]);
      setCurrentStep("documents");
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Failed to create application. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDocumentUploaded = (doc: DocumentRead) => {
    setDocuments((prev) => {
      const next = prev.filter((item) => item.id !== doc.id);
      return [...next, doc];
    });
  };

  const handleSelfieUpload = async (file: File) => {
    if (!application) return;
    setSelfieUploading(true);
    setSelfieError(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const { data } = await apiClient.post<DocumentRead>(`/kyc/applications/${application.id}/liveness`, formData);
      setSelfieDoc(data);
    } catch (error) {
      setSelfieError(error instanceof Error ? error.message : "Failed to upload selfie.");
    } finally {
      setSelfieUploading(false);
    }
  };

  const handleCompletion = async () => {
    if (!application) return;
    setCompleting(true);
    setCompletionError(null);
    try {
      const { data } = await apiClient.post<ApplicationRead>(`/kyc/applications/${application.id}/complete`);
      setApplication(data);
      setCurrentStep("success");
    } catch (error) {
      setCompletionError(error instanceof Error ? error.message : "Unable to complete profile. Please try again.");
    } finally {
      setCompleting(false);
    }
  };

  if (!user) {
    return (
      <AppShell title="Create KYC profile" description="Loading your account…">
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">Loading…</CardContent>
        </Card>
      </AppShell>
    );
  }

  return (
    <AppShell title="Create KYC profile" description="Complete the verification journey in four guided steps.">
      <StepWizard steps={steps} activeStepId={currentStep} />

      {loading ? (
        <Card>
          <CardContent className="py-10 text-center">
            <Loader2 className="mx-auto h-6 w-6 animate-spin text-muted-foreground" />
          </CardContent>
        </Card>
      ) : null}

      {!loading && currentStep === "basic" ? (
        <Card>
          <CardHeader>
            <CardTitle>Step A — Basic details</CardTitle>
            <CardDescription>Provide your legal identity and how we can reach you.</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleFormSubmit} className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="full_name">Full name</Label>
                <Input id="full_name" value={formState.full_name} onChange={(event) => setFormState({ ...formState, full_name: event.target.value })} required />
              </div>
              <div className="space-y-2">
                <Label htmlFor="parent_name">Parent/guardian name</Label>
                <Input
                  id="parent_name"
                  value={formState.parent_name}
                  onChange={(event) => setFormState({ ...formState, parent_name: event.target.value })}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="contact_number">Contact number</Label>
                <Input
                  id="contact_number"
                  value={formState.contact_number}
                  onChange={(event) => setFormState({ ...formState, contact_number: event.target.value })}
                  type="tel"
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input id="email" type="email" value={formState.email} onChange={(event) => setFormState({ ...formState, email: event.target.value })} required />
              </div>
              <div className="space-y-2">
                <Label htmlFor="nationality">Nationality</Label>
                <Input id="nationality" value={formState.nationality} onChange={(event) => setFormState({ ...formState, nationality: event.target.value })} required />
              </div>
              <div className="space-y-2">
                <Label htmlFor="pincode">Pincode</Label>
                <Input id="pincode" value={formState.pincode} onChange={(event) => setFormState({ ...formState, pincode: event.target.value })} required />
              </div>
              <div className="md:col-span-2 space-y-2">
                <Label htmlFor="address_line">Address</Label>
                <Textarea
                  id="address_line"
                  value={formState.address_line}
                  onChange={(event) => setFormState({ ...formState, address_line: event.target.value })}
                  required
                  placeholder="Flat, street, city, state"
                />
              </div>
              {formError ? (
                <div className="md:col-span-2">
                  <Alert variant="destructive">
                    <AlertDescription>{formError}</AlertDescription>
                  </Alert>
                </div>
              ) : null}
              <div className="md:col-span-2 flex justify-end">
                <Button type="submit" disabled={submitting}>
                  {submitting ? "Saving…" : "Save & continue"}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      ) : null}

      {!loading && currentStep === "documents" && application ? (
        <Card>
          <CardHeader className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <CardTitle>Step B — Upload documents</CardTitle>
              <CardDescription>Upload one document at a time. Maximum five documents before the selfie step.</CardDescription>
            </div>
            <Badge variant="outline">Application #{application.reference_id}</Badge>
          </CardHeader>
          <CardContent className="space-y-6">
            <DocumentUploadWizard applicationId={application.id} onUploadComplete={handleDocumentUploaded} />
            {documentLimitReached ? (
              <Alert>
                <AlertTitle>Limit reached</AlertTitle>
                <AlertDescription>You’ve uploaded the maximum number of documents. Continue to the selfie step.</AlertDescription>
              </Alert>
            ) : null}
            <div>
              <div className="mb-3 flex items-center justify-between">
                <p className="font-medium">Upload history</p>
                <span className="text-xs text-muted-foreground">{documents.filter((doc) => doc.doc_type !== "selfie").length}/5 documents</span>
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                {documents.length === 0 ? (
                  <p className="rounded-lg border bg-card py-6 text-center text-sm text-muted-foreground">No documents uploaded yet.</p>
                ) : (
                  documents
                    .filter((doc) => doc.doc_type !== "selfie")
                    .map((doc) => <StatusIndicator key={doc.id} status={doc.status} score={doc.authenticity_score} flags={doc.anomaly_flags} />)
                )}
              </div>
            </div>
            <div className="flex justify-end gap-3">
              <Button variant="secondary" disabled>
                Step 2 of 4
              </Button>
              <Button disabled={documents.filter((doc) => doc.doc_type !== "selfie").length === 0} onClick={() => setCurrentStep("liveness")}>
                Continue to liveliness
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : null}

      {!loading && currentStep === "liveness" && application ? (
        <Card>
          <CardHeader>
            <CardTitle>Step C — Liveliness check</CardTitle>
            <CardDescription>Upload a selfie to run through MiniFASNet V2.0 before the final review.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <SelfieDropzone onUpload={handleSelfieUpload} loading={selfieUploading} />
            {selfieError ? (
              <Alert variant="destructive">
                <AlertDescription>{selfieError}</AlertDescription>
              </Alert>
            ) : null}
            {selfieDoc ? (
              <Alert>
                <AlertTitle>Selfie uploaded</AlertTitle>
                <AlertDescription>
                  Liveness score: {(selfieDoc.liveness_score ?? 0) * 100 > 0 ? `${Math.round((selfieDoc.liveness_score ?? 0) * 100)}%` : "pending"}
                </AlertDescription>
              </Alert>
            ) : null}
            <div className="flex justify-end">
              <Button onClick={handleCompletion} disabled={!selfieDoc || completing}>
                {completing ? "Marking complete…" : "Mark profile complete"}
              </Button>
            </div>
            {completionError ? (
              <Alert variant="destructive">
                <AlertDescription>{completionError}</AlertDescription>
              </Alert>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      {!loading && currentStep === "success" && application ? (
        <SuccessPanel referenceId={application.reference_id} />
      ) : null}
    </AppShell>
  );
}

function SelfieDropzone({ onUpload, loading }: { onUpload: (file: File) => Promise<void>; loading: boolean }) {
  const [dragging, setDragging] = useState(false);

  const handleFile = (file?: File) => {
    if (!file) return;
    onUpload(file);
  };

  return (
    <label
      className={cn(
        "flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed p-10 text-center transition",
        dragging ? "border-primary bg-primary/5" : "border-muted-foreground/30",
      )}
      onDragOver={(event) => {
        event.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(event) => {
        event.preventDefault();
        setDragging(false);
        handleFile(event.dataTransfer.files?.[0]);
      }}
    >
      <input
        type="file"
        accept="image/*"
        className="hidden"
        disabled={loading}
        onChange={(event) => {
          const file = event.target.files?.[0];
          handleFile(file);
        }}
      />
      {loading ? (
        <>
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <p className="mt-3 text-sm text-muted-foreground">Uploading selfie…</p>
        </>
      ) : (
        <>
          <FileCheck2 className="h-10 w-10 text-primary" />
          <p className="mt-3 font-medium">Drop selfie here or click to browse</p>
          <p className="text-xs text-muted-foreground">We recommend a well-lit image without accessories.</p>
        </>
      )}
    </label>
  );
}

function SuccessPanel({ referenceId }: { referenceId: string }) {
  return (
    <Card className="overflow-hidden">
      <CardContent className="space-y-6 p-8 text-center">
        <div className="flex flex-col items-center gap-4">
          <div className="relative flex h-24 w-24 items-center justify-center rounded-full bg-emerald-50 text-emerald-600">
            <Sparkles className="h-10 w-10" />
            <CheckCircle2 className="absolute -bottom-2 -right-2 h-10 w-10 rounded-full bg-white text-emerald-500" />
          </div>
          <div>
            <h3 className="text-2xl font-semibold">Profile created successfully.</h3>
            <p className="mt-2 text-sm text-muted-foreground">Kindly relax with a cup of coffee while we assess your profile thoroughly.</p>
          </div>
        </div>
        <div className="rounded-xl border bg-card p-4 text-sm">
          <p className="text-muted-foreground">Reference ID</p>
          <p className="text-lg font-semibold">{referenceId}</p>
        </div>
        <div className="flex flex-wrap items-center justify-center gap-3 text-muted-foreground">
          <Coffee className="h-4 w-4" />
          Take a break — we’ll notify you once the review is complete.
        </div>
        <div className="flex justify-center">
          <Button onClick={() => (window.location.href = "/dashboard")}>Back to dashboard</Button>
        </div>
      </CardContent>
    </Card>
  );
}


