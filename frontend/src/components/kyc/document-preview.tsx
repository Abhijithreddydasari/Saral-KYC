import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import type { DocumentPreviewResponse } from "@/types/kyc";

interface DocumentPreviewProps {
  preview: DocumentPreviewResponse;
}

export function DocumentPreview({ preview }: DocumentPreviewProps) {
  const { document, download_url, mime_type } = preview;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between text-base">
          <span>{document.doc_type}</span>
          <span className="text-xs text-muted-foreground">{document.status}</span>
        </CardTitle>
        <CardDescription>ID #{document.id}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-2 text-sm">
          <div>
            <p className="text-muted-foreground">Authenticity</p>
            <p className="font-medium">{document.authenticity_score ? `${Math.round(document.authenticity_score * 100)}%` : "N/A"}</p>
          </div>
          <div>
            <p className="text-muted-foreground">Liveness</p>
            <p className="font-medium">{document.liveness_score ? `${Math.round(document.liveness_score * 100)}%` : "N/A"}</p>
          </div>
          <div>
            <p className="text-muted-foreground">Mime type</p>
            <p className="font-medium">{mime_type ?? "Unknown"}</p>
          </div>
          <div>
            <p className="text-muted-foreground">Created</p>
            <p className="font-medium">{new Date(document.created_at).toLocaleString()}</p>
          </div>
        </div>
        <Separator />
        <div className="text-xs text-muted-foreground">
          Flags: {document.anomaly_flags?.length ? document.anomaly_flags.join(", ") : "none"} • Stage weights stored in trace for downstream explainability.
        </div>
        <Button asChild variant="outline" size="sm">
          <a href={download_url} target="_blank" rel="noreferrer">
            Download
          </a>
        </Button>
      </CardContent>
    </Card>
  );
}

