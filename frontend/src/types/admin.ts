import type { ApplicationRead, DocumentRead } from "./kyc";
import type { User } from "./auth";

export interface AdminDocumentInsight {
  document_id: number;
  doc_type: string;
  extracted_fields?: Record<string, unknown> | null;
}

export interface AdminRiskProfile {
  application_id?: number | null;
  category: string;
  score: number;
  reasons: string[];
}

export interface GraphNode {
  id: string;
  label: string;
  kind: string;
  risk?: string | null;
}

export interface GraphEdge {
  source: string;
  target: string;
  label: string;
}

export interface AdminGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface AdminUserOverview {
  user: User;
  applications: ApplicationRead[];
  documents: DocumentRead[];
  insights: AdminDocumentInsight[];
  risk_profile: AdminRiskProfile;
  graph: AdminGraph;
}

export interface AdminMonitoringResponse {
  users: AdminUserOverview[];
}

