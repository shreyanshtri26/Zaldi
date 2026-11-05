export type AgentStatus = "active" | "paused" | "draft";

export interface AgentConfig {
  purpose?: string; role?: string; objective?: string; rules?: string; style?: string; languages?: string[];
  capabilities?: string[]; tools?: string[]; knowledge?: string[]; permissions?: string[]; approval_actions?: string[];
}

export interface Agent {
  id: number; name: string; description: string; icon: string; model: string; status: AgentStatus;
  config: AgentConfig; executions: number; success_rate: number | null; last_activity: string | null; updated_at: string;
}

export type AgentDraft = Pick<Agent, "name" | "description" | "icon" | "model"> & { config: AgentConfig };

export interface RunStep { label: string; status: "done" | "failed" | "running"; tool?: string; detail?: string }

export interface Product { id: number; product_name: string; price: number; color: string; brand: string; stock_quantity: number }

export interface Run {
  id: number; agent_id: number; agent_name?: string; trigger_: string; input: string;
  status: "success" | "failed" | "awaiting_approval"; steps: RunStep[]; result: string | null; error: string | null;
  duration_ms: number; created_at: string; products?: Product[];
}

export interface Policy { id: number; title: string; content: string }

export interface Approval {
  id: number; agent_id: number | null; agent_name: string | null; policy_id: number; policy_title: string; reason: string;
  current_content: string; proposed_content: string; status: "pending" | "approved" | "rejected"; created_at: string;
}
