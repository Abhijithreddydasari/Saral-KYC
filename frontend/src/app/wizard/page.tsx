"use client";

import { useMemo, useState } from "react";

import { AppShell } from "@/components/layout/app-shell";
import { StatusIndicator } from "@/components/kyc/status-indicator";
import { DocumentUploadWizard } from "@/components/applications/document-upload-wizard";
import { StepWizard } from "@/components/wizard/step-wizard";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import type { DocumentRead } from "@/types/kyc";

const wizardSteps = [
  { id: "id_card", title: "Identity proof", description: "Upload National ID, Drivers License, or Passport", docType: "id_card" },
  { id: "selfie", title: "Selfie", description: "Capture a selfie for liveness/facial match", docType: "selfie" },
];

export default function WizardPage() {
  const [applicationId, setApplicationId] = useState<number>(1);
  const [documents, setDocuments] = useState<Record<string, DocumentRead>>({});

  const handleUploaded = (doc: DocumentRead) => {
    setDocuments((prev) => ({ ...prev, [doc.doc_type.toLowerCase()]: doc }));
  };

  return (
    <AppShell title="Applicant wizard" description="Upload government documents, selfies, and track authenticity in one place.">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <Badge variant="secondary" className="mb-2">
            Resume with reference ID
          </Badge>
          <p className="text-sm text-muted-foreground">Use the reference ID from SMS/email to resume uploads any time.</p>
        </div>
        <div className="w-full max-w-xs">
          <label className="text-xs font-medium text-muted-foreground">Application ID</label>
          <Input
            type="number"
            min={1}
            value={applicationId}
            onChange={(event) => setApplicationId(Number(event.target.value) || 1)}
            className="mt-1"
          />
        </div>
      </div>

      <DocumentUploadWizard applicationId={applicationId} onUploadComplete={handleUploaded} />

      <Card>
        <CardHeader>
          <CardTitle>Upload History</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-3">
          {Object.values(documents).length === 0 ? (
            <p className="col-span-3 py-4 text-center text-sm text-muted-foreground">No documents uploaded yet.</p>
          ) : (
            Object.values(documents).map((doc) => (
              <StatusIndicator key={doc.id} status={doc.status} score={doc.authenticity_score} flags={doc.anomaly_flags} />
            ))
          )}
        </CardContent>
      </Card>
    </AppShell>
  );
}

