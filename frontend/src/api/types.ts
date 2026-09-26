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
