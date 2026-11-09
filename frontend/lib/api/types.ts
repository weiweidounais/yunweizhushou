export type Confidence = "high" | "medium" | "low";
export type Risk = "low" | "medium" | "high";

export type Hypothesis = {
  cause: string;
  confidence: Confidence;
  evidence: string[];
  falsification?: string;
};

export type Recommendation = {
  step: string;
  risk: Risk;
  requires_change: boolean;
  rollback?: string;
};

export type Assessment = {
  summary: string;
  impact?: string;
  hypotheses: Hypothesis[];
  recommendations: Recommendation[];
  unknowns?: string[];
};

export type ToolCall = {
  name: string;
  args: Record<string, unknown>;
  result_preview: string;
  status: string;
  duration_ms: number;
};

export type Usage = {
  model?: string;
  input_tokens?: number;
  output_tokens?: number;
  total_tokens?: number;
  request_id?: string | null;
};

export type ChangePlan = {
  plan_id: string;
  session_id: string;
  asset_id: string;
  action: string;
  params: Record<string, unknown>;
  reason: string;
  impact: string;
  rollback: string;
  plan_hash: string;
  status: string;
  execution?: { status?: string; summary?: string; simulated?: boolean } | null;
  verification?: { status?: string; summary?: string; checks?: string[]; simulated?: boolean } | null;
};

export type MessageView = {
  id: number;
  role: "user" | "assistant" | string;
  content: string;
  assessment?: Assessment | null;
  created_at: string;
};

export type SessionSummary = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
};

export type SessionView = {
  id: string;
  title: string;
  messages: MessageView[];
  created_at: string;
  latest_change_plan?: ChangePlan | null;
};

export type ChatResponse = {
  session_id: string;
  reply: string;
  assessment?: Assessment | null;
  tool_calls: ToolCall[];
  usage: Usage;
  warnings: string[];
  elapsed_ms: number;
  change_plan?: ChangePlan | null;
};

export type DemoCase = { id: string; question: string };

export type ApprovalResponse = {
  approval_id: string;
  expires_at: string;
  plan: ChangePlan;
};

export type AuditRecord = {
  id: number;
  ts: string;
  action: string;
  target_type: string;
  target_id: string;
  plan_hash: string;
  approval_id: string;
  result: string;
  hash: string;
};

export type AuditResponse = {
  records: AuditRecord[];
  chain: { valid: boolean; checked: number; broken_at: number | null };
};
