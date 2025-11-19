export interface DocumentRead {
  id: number;
  doc_type: string;
  status: string;
  authenticity_score?: number | null;
  liveness_score?: number | null;
  anomaly_flags?: string[] | null;
  extraction_payload?: Record<string, unknown> | null;
  model_trace?: Record<string, unknown> | null;
  created_at: string;
}

export interface ApplicationRead {
  id: number;
  reference_id: string;
  full_name: string;
  email?: string | null;
  phone_number?: string | null;
  preferred_language?: string | null;
  status: string;
  submitted_at?: string | null;
  risk_score?: number | null;
  risk_reason?: string | null;
  documents: DocumentRead[];
}

export interface RiskDecisionRead {
  id: number;
  risk_score: number;
  risk_band: string;
  rule_version: string;
  explanation: Record<string, unknown>;
  fairness_report?: Record<string, unknown> | null;
  created_at: string;
}

export interface TimelineEntry {
  event_type: string;
  message: string;
  created_at: string;
  payload?: Record<string, unknown> | null;
}

export interface ApplicationTimeline {
  application_id: number;
  status: string;
  entries: TimelineEntry[];
}

export interface ApplicationSummary {
  application: ApplicationRead;
  latest_risk?: RiskDecisionRead | null;
  timeline: ApplicationTimeline;
}

export interface DocumentPreviewResponse {
  document: DocumentRead;
  download_url: string;
  mime_type?: string | null;
  available_actions: string[];
}

export interface AssistantBootstrap {
  welcome: string;
  languages: string[];
  safety_disclaimer: string;
  suggestion_prompts: string[];
  rate_limits: Record<string, number>;
}

export interface ChatResponse {
  reply: string;
  language: string;
  safety_passed: boolean;
  metadata: Record<string, unknown>;
}

