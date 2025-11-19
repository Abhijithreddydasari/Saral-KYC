import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

interface StatusIndicatorProps {
  status: string;
  score?: number | null;
  flags?: string[] | null;
}

const STATUS_COLORS: Record<string, string> = {
  processed: "bg-emerald-600 text-white",
  processing: "bg-amber-500 text-white",
  uploaded: "bg-slate-200 text-slate-900",
  default: "bg-muted text-foreground",
};

export function StatusIndicator({ status, score, flags }: StatusIndicatorProps) {
  const normalizedStatus = status.toLowerCase();
  const badgeClass = STATUS_COLORS[normalizedStatus] ?? STATUS_COLORS.default;
  const roundedScore = typeof score === "number" ? Math.round(score * 100) : undefined;

  return (
    <div className="space-y-2 rounded-lg border bg-card p-4 text-sm">
      <div className="flex items-center justify-between">
        <Badge className={cn("capitalize", badgeClass)}>{normalizedStatus}</Badge>
        {typeof roundedScore === "number" ? <span className="text-xs text-muted-foreground">{roundedScore}% authenticity</span> : null}
      </div>
      {typeof roundedScore === "number" ? <Progress value={roundedScore} /> : null}
      {flags?.length ? (
        <div className="text-xs text-muted-foreground">
          Flags:{" "}
          {flags.map((flag) => (
            <span key={flag} className="mr-1 rounded bg-destructive/15 px-1.5 py-0.5 text-destructive">
              {flag}
            </span>
          ))}
        </div>
      ) : (
        <p className="text-xs text-muted-foreground">No anomalies reported.</p>
      )}
    </div>
  );
}

