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
    <main className="mx-auto max-w-6xl space-y-6 px-6 py-10">
      <div>
        <p className="text-sm text-muted-foreground">Operations console</p>
        <h1 className="text-3xl font-semibold">Review applications, risk, and assistant chat</h1>
      </div>
      {applications.length ? (
        <StaffDashboard applications={applications} initialSummary={initialSummary} />
      ) : (
        <p className="rounded-xl border bg-card p-6 text-sm text-muted-foreground">No applications found. Create one via the API first.</p>
      )}
    </main>
  );
}

