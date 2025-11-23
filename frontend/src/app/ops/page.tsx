import { AppShell } from "@/components/layout/app-shell";
import { StaffDashboard } from "@/components/dashboard/staff-dashboard";
import { apiClient } from "@/lib/api-client";
import type { ApplicationRead, ApplicationSummary } from "@/types/kyc";

export const revalidate = 0;

export default async function OpsPage() {
  let applications: ApplicationRead[] = [];
  let initialSummary: ApplicationSummary | null = null;

  try {
    const appsResponse = await apiClient.get<ApplicationRead[]>("/kyc/applications");
    applications = appsResponse.data;
    if (applications.length) {
      const summaryResponse = await apiClient.get<ApplicationSummary>(`/kyc/applications/${applications[0].id}/summary`);
      initialSummary = summaryResponse.data;
    }
  } catch (err) {
    console.error("Failed to load applications", err);
  }

  return (
    <AppShell title="Operations console" description="Review applications, risk, and assistant chat">
      {applications.length ? (
        <StaffDashboard applications={applications} initialSummary={initialSummary} />
      ) : (
        <p className="rounded-xl border bg-card p-6 text-sm text-muted-foreground">No applications found. Create one via the API first.</p>
      )}
    </AppShell>
  );
}

