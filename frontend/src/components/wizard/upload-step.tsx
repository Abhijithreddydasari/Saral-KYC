"use client";

import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";
import { apiClient } from "@/lib/api-client";
import type { DocumentRead } from "@/types/kyc";

interface UploadStepProps {
  applicationId: number;
  docType: string;
  label: string;
  description?: string;
  onUploaded?: (document: DocumentRead) => void;
}

export function UploadStep({ applicationId, docType, label, description, onUploaded }: UploadStepProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [fileName, setFileName] = useState<string>();
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState<"idle" | "success" | "error">("idle");
  const [error, setError] = useState<string>();

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) {
      setFileName(undefined);
      return;
    }
    setFileName(file.name);
    setStatus("idle");
    setError(undefined);
  };

  const handleUpload = async () => {
    const file = inputRef.current?.files?.[0];
    if (!file) {
      setError("Attach a file first");
      return;
    }
    setUploading(true);
    setProgress(10);
    setError(undefined);

    const interval = window.setInterval(() => {
      setProgress((prev) => (prev < 85 ? prev + 5 : prev));
    }, 200);

    try {
      const form = new FormData();
      form.append("doc_type", docType);
      form.append("file", file);

      const { data } = await apiClient.post<DocumentRead>(`/kyc/applications/${applicationId}/documents`, form);
      setStatus("success");
      setProgress(100);
      onUploaded?.(data);
    } catch (err) {
      console.error(err);
      setStatus("error");
      setError(err instanceof Error ? err.message : "Upload failed");
      setProgress(0);
    } finally {
      window.clearInterval(interval);
      setUploading(false);
      if (inputRef.current) {
        inputRef.current.value = "";
      }
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>{label}</CardTitle>
        {description ? <CardDescription>{description}</CardDescription> : null}
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label className="text-sm font-medium text-muted-foreground">Upload document</Label>
          <div className="flex flex-col gap-3 rounded-lg border border-dashed border-muted-foreground/30 bg-muted/30 p-4 text-sm">
            <Input ref={inputRef} type="file" accept="image/*,.pdf" onChange={handleFileChange} disabled={uploading} />
            <span className="text-muted-foreground">{fileName ?? "Choose PNG, JPG, or PDF up to 5 MB."}</span>
          </div>
        </div>

        {uploading || status === "success" ? (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm text-muted-foreground">
              <span>{uploading ? "Uploading…" : "Processed"}</span>
              <span>{progress}%</span>
            </div>
            <Progress value={progress} />
          </div>
        ) : null}

        {error ? <p className="text-sm text-destructive">{error}</p> : null}

        <div className="flex items-center gap-3">
          <Button onClick={handleUpload} disabled={uploading} className={cn(status === "success" && "bg-emerald-600 hover:bg-emerald-600/90")}>
            {status === "success" ? "Uploaded" : "Upload"}
          </Button>
          {status === "success" ? <span className="text-sm text-muted-foreground">Stage complete.</span> : null}
        </div>
      </CardContent>
    </Card>
  );
}

