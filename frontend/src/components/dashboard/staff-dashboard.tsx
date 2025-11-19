"use client";

import { useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import { apiClient } from "@/lib/api-client";
import type {
  ApplicationRead,
  ApplicationSummary,
  AssistantBootstrap,
  ChatResponse,
  DocumentPreviewResponse,
  DocumentRead,
  TimelineEntry,
} from "@/types/kyc";
import { DocumentPreview } from "@/components/kyc/document-preview";

interface StaffDashboardProps {
  applications: ApplicationRead[];
  initialSummary?: ApplicationSummary | null;
}

export function StaffDashboard({ applications, initialSummary }: StaffDashboardProps) {
  const [selectedAppId, setSelectedAppId] = useState(initialSummary?.application.id ?? applications[0]?.id);
  const [summary, setSummary] = useState<ApplicationSummary | null>(initialSummary ?? null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>();

  useEffect(() => {
    if (!selectedAppId) return;
    if (initialSummary && initialSummary.application.id === selectedAppId) return;
    let cancelled = false;
    const fetchSummary = async () => {
      setLoading(true);
      setError(undefined);
      try {
        const { data } = await apiClient.get<ApplicationSummary>(`/kyc/applications/${selectedAppId}/summary`);
        if (!cancelled) {
          setSummary(data);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load summary");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };
    fetchSummary();
    return () => {
      cancelled = true;
    };
  }, [selectedAppId, initialSummary]);

  const activeApplication = useMemo(() => applications.find((app) => app.id === selectedAppId), [applications, selectedAppId]);

  return (
    <div className="grid gap-6 lg:grid-cols-[280px_1fr]">
      <aside className="space-y-3 rounded-xl border bg-card p-4">
        <h2 className="text-sm font-semibold text-muted-foreground">Applications</h2>
        <div className="space-y-2">
          {applications.map((app) => (
            <button
              key={app.id}
              onClick={() => setSelectedAppId(app.id)}
              className={cn(
                "w-full rounded-lg border p-3 text-left text-sm transition",
                app.id === selectedAppId ? "border-primary bg-primary/10" : "border-muted hover:border-primary/40",
              )}
            >
              <p className="font-medium">{app.full_name}</p>
              <p className="text-xs text-muted-foreground">{app.reference_id}</p>
            </button>
          ))}
        </div>
      </aside>

      <section className="space-y-6">
        {error ? (
          <Card>
            <CardContent className="py-6 text-sm text-destructive">{error}</CardContent>
          </Card>
        ) : null}
        <Card>
          <CardHeader>
            <CardTitle className="text-xl">{activeApplication?.full_name ?? "Select an application"}</CardTitle>
            <CardDescription>
              {activeApplication
                ? `${activeApplication.documents.length} documents · status ${activeApplication.status}`
                : "Choose an application on the left to load telemetry."}
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-3">
            <Metric label="Risk score" value={summary?.latest_risk ? `${Math.round(summary.latest_risk.risk_score * 100)}%` : "N/A"} />
            <Metric label="Risk band" value={summary?.latest_risk?.risk_band ?? "Pending"} />
            <Metric label="Last timeline event" value={summary?.timeline.entries[0]?.message ?? "Not started"} />
          </CardContent>
        </Card>

        <div className="grid gap-4 lg:grid-cols-3">
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle>Timeline</CardTitle>
            </CardHeader>
            <CardContent>
              <Timeline entries={summary?.timeline.entries ?? []} />
            </CardContent>
          </Card>
          <AssistantPanel applicationReference={summary?.application.reference_id} />
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <DocumentGallery documents={summary?.application.documents ?? []} applicationId={summary?.application.id} />
          <RiskFactorsPanel summary={summary} loading={loading} />
        </div>
      </section>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border bg-muted/40 p-3 text-sm">
      <p className="text-muted-foreground">{label}</p>
      <p className="text-lg font-semibold">{value}</p>
    </div>
  );
}

function Timeline({ entries }: { entries: TimelineEntry[] }) {
  if (!entries.length) {
    return <p className="text-sm text-muted-foreground">No events logged yet.</p>;
  }
  return (
    <ol className="space-y-4">
      {entries.map((entry) => (
        <li key={entry.created_at} className="relative pl-6">
          <span className="absolute left-0 top-1 h-2 w-2 rounded-full bg-primary" />
          <p className="text-sm font-medium">{entry.message}</p>
          <p className="text-xs text-muted-foreground">{new Date(entry.created_at).toLocaleString()}</p>
        </li>
      ))}
    </ol>
  );
}

function RiskFactorsPanel({ summary, loading }: { summary: ApplicationSummary | null; loading: boolean }) {
  const factors = summary?.latest_risk?.explanation?.factors;
  return (
    <Card>
      <CardHeader>
        <CardTitle>Risk explainability</CardTitle>
        <CardDescription>Live from risk engine SHAP-like payload.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        {loading ? <p className="text-muted-foreground">Loading…</p> : null}
        {!loading && !factors ? <p className="text-muted-foreground">No decision yet.</p> : null}
        {Array.isArray(factors)
          ? factors.map((factor: any) => (
              <div key={factor.id} className="rounded-lg border p-3">
                <div className="flex items-center justify-between">
                  <p className="font-medium">{factor.id.replace("_", " ")}</p>
                  <Badge variant={factor.weight >= 0 ? "secondary" : "destructive"}>{factor.value}</Badge>
                </div>
                <p className="text-xs text-muted-foreground">{factor.detail}</p>
              </div>
            ))
          : null}
      </CardContent>
    </Card>
  );
}

function DocumentGallery({ documents, applicationId }: { documents: DocumentRead[]; applicationId?: number }) {
  const [activeDocId, setActiveDocId] = useState<number | null>(documents[0]?.id ?? null);
  const [preview, setPreview] = useState<DocumentPreviewResponse>();
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!applicationId || !activeDocId) return;
    let cancelled = false;
    const fetchPreview = async () => {
      setLoading(true);
      try {
        const { data } = await apiClient.get<DocumentPreviewResponse>(`/kyc/applications/${applicationId}/documents/${activeDocId}/preview`);
        if (!cancelled) {
          setPreview(data);
        }
      } catch (err) {
        console.error(err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    fetchPreview();
    return () => {
      cancelled = true;
    };
  }, [activeDocId, applicationId]);

  if (!documents.length) {
    return (
      <Card>
        <CardContent className="py-6 text-sm text-muted-foreground">No documents uploaded yet.</CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        {documents.map((doc) => (
          <Button key={doc.id} variant={doc.id === activeDocId ? "default" : "outline"} size="sm" onClick={() => setActiveDocId(doc.id)}>
            {doc.doc_type}
          </Button>
        ))}
      </div>
      {loading && <p className="text-sm text-muted-foreground">Loading preview…</p>}
      {preview ? <DocumentPreview preview={preview} /> : null}
    </div>
  );
}

function AssistantPanel({ applicationReference }: { applicationReference?: string }) {
  const [bootstrap, setBootstrap] = useState<AssistantBootstrap>();
  const [messages, setMessages] = useState<{ role: "user" | "assistant"; content: string }[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);

  useEffect(() => {
    apiClient
      .get<AssistantBootstrap>("/assist/session/bootstrap")
      .then(({ data }) => setBootstrap(data))
      .catch((err) => console.error(err));
  }, []);

  const sendMessage = async () => {
    if (!input.trim()) return;
    const content = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content }]);
    setSending(true);
    try {
      const { data } = await apiClient.post<ChatResponse>("/assist/chat", {
        message: content,
        application_reference_id: applicationReference,
      });
      setMessages((prev) => [...prev, { role: "assistant", content: data.reply }]);
    } catch (err) {
      setMessages((prev) => [...prev, { role: "assistant", content: "Something went wrong. Please try again." }]);
      console.error(err);
    } finally {
      setSending(false);
    }
  };

  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle>Assistant</CardTitle>
        <CardDescription>{bootstrap?.welcome ?? "Loading assistant metadata…"}</CardDescription>
      </CardHeader>
      <CardContent className="flex h-full flex-col gap-3">
        <div className="flex-1 space-y-3 rounded-lg border bg-muted/40 p-3 text-sm">
          {messages.length === 0 ? <p className="text-muted-foreground">Ask for document status, nudges, or escalations.</p> : null}
          {messages.map((msg, idx) => (
            <div key={idx} className={cn("rounded-lg px-3 py-2", msg.role === "assistant" ? "bg-muted text-foreground" : "bg-primary text-primary-foreground")}>
              {msg.content}
            </div>
          ))}
        </div>
        <Textarea value={input} onChange={(event) => setInput(event.target.value)} placeholder="Type a question…" disabled={sending} />
        <Button onClick={sendMessage} disabled={sending}>
          {sending ? "Sending…" : "Send"}
        </Button>
        {bootstrap?.suggestion_prompts?.length ? (
          <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
            Suggestions:
            {bootstrap.suggestion_prompts.map((suggestion) => (
              <button
                key={suggestion}
                className="rounded-full border px-3 py-1 text-[11px]"
                onClick={() => setInput(suggestion)}
                type="button"
              >
                {suggestion}
              </button>
            ))}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

