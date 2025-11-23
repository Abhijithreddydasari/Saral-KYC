"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowUpRight, CheckCircle2, Loader2, ShieldHalf, UserCog } from "lucide-react";

import { AppShell } from "@/components/layout/app-shell";
import { useAuth } from "@/components/providers/auth-provider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { apiClient } from "@/lib/api-client";
import type { ApplicationRead, RiskStatusResponse } from "@/types/kyc";

export default function DashboardPage() {
  const router = useRouter();
  const { user, loading } = useAuth();
  const [application, setApplication] = useState<ApplicationRead | null>(null);
  const [appLoading, setAppLoading] = useState(true);
  const [statusRequested, setStatusRequested] = useState(false);
  const [countdown, setCountdown] = useState(10);
  const [status, setStatus] = useState<RiskStatusResponse | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
    }
  }, [loading, router, user]);

  useEffect(() => {
    if (!user) return;
    const loadApplication = async () => {
      setAppLoading(true);
      try {
        const { data } = await apiClient.get<ApplicationRead[]>("/kyc/applications/mine");
        setApplication(data[0] ?? null);
      } catch (error) {
        console.error("Failed to load application", error);
      } finally {
        setAppLoading(false);
      }
    };
    loadApplication();
  }, [user]);

  useEffect(() => {
    if (!statusRequested || status || countdown === 0) return;
    const timer = setTimeout(() => setCountdown((prev) => Math.max(prev - 1, 0)), 1000);
    return () => clearTimeout(timer);
  }, [statusRequested, countdown, status]);

  useEffect(() => {
    if (!statusRequested || countdown !== 0 || status || !application) return;
    const fetchStatus = async () => {
      try {
        const { data } = await apiClient.get<RiskStatusResponse>(`/kyc/applications/${application.id}/risk/status`);
        setStatus(data);
      } catch (error) {
        setStatusError(error instanceof Error ? error.message : "Unable to fetch status.");
      }
    };
    fetchStatus();
  }, [application, countdown, status, statusRequested]);

  const triggerStatusCheck = () => {
    if (!application) return;
    setStatus(null);
    setStatusError(null);
    setCountdown(10);
    setStatusRequested(true);
  };

  if (!user) {
    return (
      <AppShell title="Dashboard" description="Loading your workspace...">
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">Checking your session…</CardContent>
        </Card>
      </AppShell>
    );
  }

  const profileComplete = Boolean(application?.completed_at);

  return (
    <AppShell title="Unified dashboard" description="Track onboarding tasks, risk status, and assistant threads.">
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between gap-3">
            <div>
              <CardTitle>Create KYC Profile</CardTitle>
              <CardDescription>Multi-step wizard for applicant onboarding.</CardDescription>
            </div>
            {profileComplete ? <CheckCircle2 className="h-6 w-6 text-emerald-500" /> : <ShieldHalf className="h-5 w-5 text-primary" />}
          </CardHeader>
          <CardContent className="space-y-3">
            {application ? (
              <Badge variant="outline">Reference #{application.reference_id}</Badge>
            ) : (
              <p className="text-xs text-muted-foreground">No profile yet. Start with the guided wizard.</p>
            )}
            <Button asChild className="w-full" disabled={profileComplete || appLoading}>
              <Link href="/kyc/create">{profileComplete ? "Profile completed" : "Start / resume flow"}</Link>
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>KYC Status</CardTitle>
            <CardDescription>Reveal the risk category with a 10-second animation.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {!application ? (
              <p className="text-sm text-muted-foreground">Create a profile first to check risk.</p>
            ) : status ? (
              <div className="space-y-2">
                <Badge className={statusBadgeClass(status.category)}>{status.category.toUpperCase()}</Badge>
                <p className="text-sm text-muted-foreground">Score: {Math.round(status.score * 100)}%</p>
                {status.reasons.map((reason) => (
                  <p key={reason} className="rounded-lg border border-border/60 bg-card/60 p-2 text-xs">
                    {reason}
                  </p>
                ))}
              </div>
            ) : statusRequested ? (
              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Revealing in…</span>
                  <span>{countdown}s</span>
                </div>
                <Progress value={((10 - countdown) / 10) * 100} />
              </div>
            ) : (
              <p className="text-xs text-muted-foreground">Click below to simulate the status fetch.</p>
            )}
            {statusError ? <p className="text-xs text-red-500">{statusError}</p> : null}
            <Button className="w-full" disabled={!application || (statusRequested && countdown > 0)} onClick={triggerStatusCheck}>
              {!application ? "Create profile first" : statusRequested && countdown > 0 ? `Revealing in ${countdown}s` : "Check status"}
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Chat with LLM</CardTitle>
            <CardDescription>Multilingual assistant with streaming replies.</CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild className="w-full">
              <Link href="/assistant">
                Launch chat <ArrowUpRight className="ml-2 h-4 w-4" />
              </Link>
            </Button>
          </CardContent>
        </Card>

        {user.is_admin ? (
          <Card>
            <CardHeader className="flex flex-row items-center justify-between gap-3">
              <div>
                <CardTitle>Admin Monitoring</CardTitle>
                <CardDescription>Graph network + risk insights across all users.</CardDescription>
              </div>
              <UserCog className="h-5 w-5 text-primary" />
            </CardHeader>
            <CardContent className="space-y-3">
              <Button asChild className="w-full">
                <Link href="/admin/monitoring">
                  Open admin view <ArrowUpRight className="ml-2 h-4 w-4" />
                </Link>
              </Button>
              <Badge variant="outline">Demo admin — admin@saral / Admin!23</Badge>
            </CardContent>
          </Card>
        ) : null}
      </div>
    </AppShell>
  );
}

function statusBadgeClass(category: string) {
  switch (category) {
    case "safe":
      return "bg-emerald-500/15 text-emerald-600 border border-emerald-500/40";
    case "medium":
      return "bg-amber-500/15 text-amber-600 border border-amber-500/40";
    case "high":
      return "bg-red-500/15 text-red-600 border border-red-500/40";
    default:
      return "";
  }
}

