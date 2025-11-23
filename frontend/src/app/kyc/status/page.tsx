"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AlertCircle, Clock3, ShieldCheck } from "lucide-react";

import { AppShell } from "@/components/layout/app-shell";
import { useAuth } from "@/components/providers/auth-provider";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { apiClient } from "@/lib/api-client";
import type { ApplicationRead, RiskStatusResponse } from "@/types/kyc";

const STATUS_COLORS: Record<string, string> = {
  safe: "bg-emerald-500/15 text-emerald-600 border-emerald-500/30",
  medium: "bg-amber-500/15 text-amber-600 border-amber-500/30",
  high: "bg-red-500/15 text-red-600 border-red-500/30",
};

export default function KycStatusPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [application, setApplication] = useState<ApplicationRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [countdown, setCountdown] = useState(10);
  const [status, setStatus] = useState<RiskStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && !user) {
      router.replace("/login");
    }
  }, [authLoading, router, user]);

  useEffect(() => {
    if (!user) return;
    const loadApplication = async () => {
      try {
        const { data } = await apiClient.get<ApplicationRead[]>("/kyc/applications/mine");
        setApplication(data[0] ?? null);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    loadApplication();
  }, [user]);

  useEffect(() => {
    if (!application || status || countdown === 0) return;
    const timer = setTimeout(() => setCountdown((prev) => Math.max(prev - 1, 0)), 1000);
    return () => clearTimeout(timer);
  }, [application, countdown, status]);

  useEffect(() => {
    if (!application || countdown !== 0 || status) return;
    const fetchStatus = async () => {
      try {
        const { data } = await apiClient.get<RiskStatusResponse>(`/kyc/applications/${application.id}/risk/status`);
        setStatus(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to fetch risk status.");
      }
    };
    fetchStatus();
  }, [application, countdown, status]);

  if (!user) {
    return (
      <AppShell title="KYC Status" description="Loading session…">
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">Loading…</CardContent>
        </Card>
      </AppShell>
    );
  }

  if (loading) {
    return (
      <AppShell title="KYC Status" description="Checking your application…">
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">Fetching application…</CardContent>
        </Card>
      </AppShell>
    );
  }

  if (!application) {
    return (
      <AppShell title="KYC Status" description="You haven't created a profile yet.">
        <Alert>
          <AlertDescription>
            No application found. Start the{" "}
            <Button variant="link" className="px-0" onClick={() => router.push("/kyc/create")}>
              KYC creation flow
            </Button>{" "}
            first.
          </AlertDescription>
        </Alert>
      </AppShell>
    );
  }

  return (
    <AppShell title="KYC Status" description="Risk assessment updates based on uploaded documents and liveness.">
      <Card>
        <CardHeader>
          <CardTitle>Application #{application.reference_id}</CardTitle>
          <CardDescription>We simulate a delay to mimic real-world risk computations.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {!status ? (
            <>
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Preparing risk summary…</span>
                <span>{countdown}s</span>
              </div>
              <Progress value={((10 - countdown) / 10) * 100} />
              <p className="text-xs text-muted-foreground">Hang tight for ~10 seconds while we crunch the numbers.</p>
            </>
          ) : (
            <>
              <div className="flex items-center gap-3">
                <Badge className={STATUS_COLORS[status.category] ?? ""}>{status.category.toUpperCase()}</Badge>
                <span className="text-sm text-muted-foreground">Score: {Math.round(status.score * 100)}%</span>
              </div>
              <div className="space-y-3">
                {status.reasons.map((reason) => (
                  <div key={reason} className="rounded-lg border border-border/60 bg-card/60 p-3 text-sm">
                    {reason}
                  </div>
                ))}
              </div>
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <ShieldCheck className="h-4 w-4" />
                Generated at {new Date(status.generated_at).toLocaleString()}
              </div>
            </>
          )}
          {error ? (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          ) : null}
        </CardContent>
      </Card>

      {!status ? (
        <Card>
          <CardHeader>
            <CardTitle>What happens during the wait?</CardTitle>
            <CardDescription>We orchestrate forgery detection, metadata drift, and network graph insights.</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
            <Clock3 className="h-4 w-4" />
            Document authenticity, liveliness, and graph scoring run sequentially. This preview waits ~10 seconds so the dashboard button can animate the reveal.
          </CardContent>
        </Card>
      ) : null}
    </AppShell>
  );
}

