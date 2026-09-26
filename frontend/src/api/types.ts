// Response shapes, mirroring API_CONTRACT.md. Edit the contract first, then these.

export interface Health {
  status: string;
  app_version: string;
  prd_version: string;
}

export type EffortLevel = "low" | "medium" | "high" | "xhigh" | "max";

export interface Settings {
  owner_name: string;
  model: string;
  effort: EffortLevel | string;
  verifier_enabled: boolean;
  web_research_enabled: boolean;
  key_set: boolean;
  key_last4: string;
}

export interface ConnectionTest {
  key_valid: boolean;
  model_available: boolean;
  capabilities: { pdf_input: boolean; structured_outputs: boolean };
  message: string;
}

export interface ModelSummary {
  id: string;
  display_name: string;
  pdf_input: boolean;
  structured_outputs: boolean;
  effort_levels: string[];
}

export interface ModelChoices {
  models: ModelSummary[];
  from_anthropic: boolean;
  message: string;
}

export interface ModelUpdate {
  model: string;
  effort: string;
  verifier_enabled: boolean;
}

export interface ScopeFields {
  name?: string;
  process_name?: string;
  trigger?: string;
  end_point?: string;
  in_scope_roles?: string[];
  out_of_scope?: string;
  process_kpi?: string;
  industry?: string;
  adjacent_industries?: string[];
  confidential_terms?: string[];
}

export interface Engagement {
  id: string;
  name: string;
  process_name: string;
  trigger: string;
  end_point: string;
  in_scope_roles: string[];
  out_of_scope: string;
  process_kpi: string;
  industry: string;
  adjacent_industries: string[];
  confidential_terms: string[];
  status: string;
  created_at: string;
  updated_at: string;
}

export interface EngagementSummary extends Engagement {
  latest_version: { label: string; state: string } | null;
  review_progress: { reviewed: number; total: number };
  sources_count: number;
}

export type NavKey =
  | "setup"
  | "sources"
  | "draft"
  | "review"
  | "published"
  | "matrix"
  | "gap_analysis"
  | "registers"
  | "leadership"
  | "exports";

export type NavState = "done" | "attention" | "not_started";

export interface Readiness {
  key_set: boolean;
  transcripts_ready: boolean;
  documents_ready: boolean;
  speakers_unmapped: number;
  draft_exists: boolean;
  blockers_count: number;
  nav: Record<NavKey, NavState>;
  nav_counts: Partial<Record<NavKey, number>>;
  next_step: NavKey | null;
  missing: string[];
  ready_to_draft: boolean;
}

export interface Role {
  id: string;
  engagement_id: string;
  name: string;
  aliases: string[];
  is_system: boolean;
  lane_order: number | null;
}

export interface RoleCreate {
  name: string;
  aliases?: string[];
  is_system?: boolean;
}

export type RolePatch = Partial<Pick<Role, "name" | "aliases" | "is_system">> & { lane_order?: number };
