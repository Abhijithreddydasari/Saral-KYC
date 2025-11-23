"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AlertCircle, Loader2 } from "lucide-react";

import { AppShell } from "@/components/layout/app-shell";
import { useAuth } from "@/components/providers/auth-provider";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { apiClient } from "@/lib/api-client";
import type { AdminMonitoringResponse, AdminUserOverview, AdminGraph, GraphNode } from "@/types/admin";

export default function AdminMonitoringPage() {
  const router = useRouter();
  const { user, loading } = useAuth();
  const [data, setData] = useState<AdminMonitoringResponse | null>(null);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [fetching, setFetching] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && (!user || !user.is_admin)) {
      router.replace("/dashboard");
    }
  }, [loading, router, user]);

  useEffect(() => {
    if (!user?.is_admin) return;
    const load = async () => {
      setFetching(true);
      setError(null);
      try {
        const { data } = await apiClient.get<AdminMonitoringResponse>("/admin/overview");
        setData(data);
        setSelectedIndex(0);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to load monitoring data.");
      } finally {
        setFetching(false);
      }
    };
    load();
  }, [user]);

  if (!user || !user.is_admin) {
    return (
      <AppShell title="Admin monitoring" description="Restricted to Saral admins.">
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">Redirecting…</CardContent>
        </Card>
      </AppShell>
    );
  }

  return (
    <AppShell title="Admin monitoring" description="Documents, insights, and graph neural context across applicants.">
      {error ? (
        <Card>
          <CardContent className="flex items-center gap-2 py-4 text-sm text-destructive">
            <AlertCircle className="h-4 w-4" /> {error}
          </CardContent>
        </Card>
      ) : null}

      {fetching ? (
        <Card>
          <CardContent className="flex items-center justify-center gap-2 py-10 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading network telemetry…
          </CardContent>
        </Card>
      ) : null}

      {data && data.users.length ? (
        <div className="grid gap-4 lg:grid-cols-[240px_1fr]">
          <Card>
            <CardHeader>
              <CardTitle>Users</CardTitle>
              <CardDescription>Select an applicant to review.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              {data.users.map((snapshot, index) => (
                <button
                  key={snapshot.user.id}
                  onClick={() => setSelectedIndex(index)}
                  className={`w-full rounded-lg border p-3 text-left text-sm transition ${
                    index === selectedIndex ? "border-primary bg-primary/10" : "border-border hover:border-primary/50"
                  }`}
                >
                  <p className="font-medium">{snapshot.user.full_name}</p>
                  <p className="text-xs text-muted-foreground">{snapshot.user.email}</p>
                </button>
              ))}
            </CardContent>
          </Card>

          <AdminDetail snapshot={data.users[selectedIndex]} />
        </div>
      ) : null}
    </AppShell>
  );
}

function AdminDetail({ snapshot }: { snapshot: AdminUserOverview }) {
  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <CardTitle>{snapshot.user.full_name}</CardTitle>
            <CardDescription>{snapshot.user.email}</CardDescription>
          </div>
          <Badge className={statusBadge(snapshot.risk_profile.category, true)}>{snapshot.risk_profile.category.toUpperCase()}</Badge>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-3">
          <Metric label="Applications" value={snapshot.applications.length} />
          <Metric label="Documents" value={snapshot.documents.length} />
          <Metric label="Risk score" value={`${Math.round(snapshot.risk_profile.score * 100)}%`} />
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Risk explainability</CardTitle>
            <CardDescription>Top triggers for the latest decision.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {snapshot.risk_profile.reasons.map((reason) => (
              <div key={reason} className="rounded-lg border border-border/60 bg-card/60 p-3 text-sm">
                {reason}
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Graph neural view</CardTitle>
            <CardDescription>User as the central node with level-2 neighbors.</CardDescription>
          </CardHeader>
          <CardContent>
            <GraphView graph={snapshot.graph} />
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Documents</CardTitle>
          <CardDescription>Latest authenticity & anomaly flags.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {snapshot.documents.length === 0 ? (
            <p className="text-sm text-muted-foreground">No documents uploaded.</p>
          ) : (
            snapshot.documents.map((doc) => (
              <div key={doc.id} className="rounded-lg border border-border/60 bg-card/60 p-3 text-sm">
                <div className="flex items-center justify-between">
                  <p className="font-medium uppercase">{doc.doc_type}</p>
                  <Badge variant="outline">{doc.status}</Badge>
                </div>
                <p className="text-xs text-muted-foreground">
                  Authenticity: {doc.authenticity_score ? `${Math.round(doc.authenticity_score * 100)}%` : "pending"}
                </p>
                {doc.anomaly_flags?.length ? (
                  <p className="text-xs text-red-500">Flags: {doc.anomaly_flags.join(", ")}</p>
                ) : (
                  <p className="text-xs text-muted-foreground">No anomalies.</p>
                )}
              </div>
            ))
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Insights</CardTitle>
          <CardDescription>Extracted fields per document.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          {snapshot.insights.length === 0 ? (
            <p className="text-sm text-muted-foreground">No structured insights yet.</p>
          ) : (
            snapshot.insights.map((insight) => (
              <div key={`${insight.document_id}-${insight.doc_type}`} className="rounded-lg border border-border/60 bg-card/60 p-3 text-xs">
                <p className="font-medium uppercase">{insight.doc_type}</p>
                <Separator className="my-2" />
                <pre className="whitespace-pre-wrap text-[11px] text-muted-foreground">
                  {JSON.stringify(insight.extracted_fields ?? {}, null, 2)}
                </pre>
              </div>
            ))
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function GraphView({ graph }: { graph: AdminGraph }) {
  const size = 280;
  const center = size / 2;
  const radius = size / 2 - 40;
  const positions = new Map<string, { x: number; y: number }>();
  const userNode = graph.nodes.find((node) => node.kind === "user");

  if (userNode) {
    positions.set(userNode.id, { x: center, y: center });
  }

  const otherNodes = graph.nodes.filter((node) => node.kind !== "user");
  otherNodes.forEach((node, index) => {
    const angle = (index / Math.max(otherNodes.length, 1)) * Math.PI * 2;
    positions.set(node.id, {
      x: center + radius * Math.cos(angle),
      y: center + radius * Math.sin(angle),
    });
  });

  return (
    <svg width={size} height={size} className="w-full">
      {graph.edges.map((edge) => {
        const from = positions.get(edge.source);
        const to = positions.get(edge.target);
        if (!from || !to) return null;
        return <line key={`${edge.source}-${edge.target}`} x1={from.x} y1={from.y} x2={to.x} y2={to.y} stroke="#cbd5f5" strokeWidth={1.5} strokeDasharray="4 2" />;
      })}
      {graph.nodes.map((node) => {
        const pos = positions.get(node.id);
        if (!pos) return null;
        const color = nodeColor(node);
        return (
          <g key={node.id} transform={`translate(${pos.x}, ${pos.y})`}>
            <circle r={node.kind === "user" ? 18 : 12} fill={color.bg} stroke={color.border} strokeWidth={2} />
            <text textAnchor="middle" dy={4} fontSize={10} fill={color.text}>
              {node.label.slice(0, 6)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

function nodeColor(node: GraphNode) {
  if (node.kind === "user") {
    return { bg: "#2563eb22", border: "#2563eb", text: "#1d4ed8" };
  }
  if (node.kind === "risk" || node.risk === "high") {
    return { bg: "#f8717133", border: "#f87171", text: "#b91c1c" };
  }
  if (node.kind === "flag") {
    return { bg: "#fbbf2433", border: "#f59e0b", text: "#b45309" };
  }
  return { bg: "#94a3b833", border: "#94a3b8", text: "#475569" };
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border border-border/60 bg-card/60 p-3 text-sm">
      <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="text-lg font-semibold">{value}</p>
    </div>
  );
}

function statusBadge(category: string, filled = false) {
  const base = filled ? "" : "border ";
  switch (category) {
    case "safe":
      return `${base}bg-emerald-500/15 text-emerald-600 border-emerald-500/30`;
    case "medium":
      return `${base}bg-amber-500/15 text-amber-600 border-amber-500/30`;
    case "high":
      return `${base}bg-red-500/15 text-red-600 border-red-500/30`;
    default:
      return base;
  }
}

