import type { Agent, AgentDraft, Approval, Policy, Run } from "../types";

const KEY = "zaldi_admin_web";
const SID = "zaldi_session_web";

export const tokenStore = {
  get: () => { try { return sessionStorage.getItem(KEY) ?? ""; } catch { return ""; } },
  set: (t: string) => { try { sessionStorage.setItem(KEY, t); } catch { /* storage blocked */ } },
  clear: () => { try { sessionStorage.removeItem(KEY); } catch { /* storage blocked */ } },
};

function sessionId(): string {
  try {
    let id = localStorage.getItem(SID);
    if (!id) { id = crypto.randomUUID(); localStorage.setItem(SID, id); }
    return id;
  } catch { return crypto.randomUUID(); }
}

export class ApiError extends Error {
  constructor(message: string, readonly status: number) { super(message); }
}

async function call<T>(path: string, init: RequestInit = {}, token = tokenStore.get()): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", "X-Admin-Token": token, "X-Session-Id": sessionId(), ...init.headers },
    });
  } catch {
    throw new ApiError("Cannot reach the server. Is the backend running?", 0);
  }
  if (res.status === 204) return undefined as T;
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(body.error ?? `Request failed (${res.status})`, res.status);
  return body as T;
}

const json = (method: string, body?: unknown): RequestInit => ({ method, body: body === undefined ? undefined : JSON.stringify(body) });

export const api = {
  login: (token: string) => call("/admin/login", json("POST"), token),
  agents: () => call<{ agents: Agent[] }>("/admin/agents").then((r) => r.agents),
  agent: (id: number) => call<Agent>(`/admin/agents/${id}`),
  createAgent: (d: AgentDraft & { status?: string }) => call<Agent>("/admin/agents", json("POST", d)),
  updateAgent: (id: number, d: Partial<AgentDraft> & { status?: string }) => call<Agent>(`/admin/agents/${id}`, json("PATCH", d)),
  deleteAgent: (id: number) => call<void>(`/admin/agents/${id}`, json("DELETE")),
  duplicateAgent: (id: number) => call<Agent>(`/admin/agents/${id}/duplicate`, json("POST")),
  testAgent: (id: number, message: string) => call<Run>(`/admin/agents/${id}/test`, json("POST", { message })),
  runs: (agentId?: number) => call<{ runs: Run[] }>(`/admin/runs${agentId ? `?agent_id=${agentId}` : ""}`).then((r) => r.runs),
  approvals: (status = "") => call<{ approvals: Approval[] }>(`/admin/approvals?status=${status}`).then((r) => r.approvals),
  propose: (policy_id: number, proposed_content: string, reason: string, agent_id?: number) =>
    call<Approval>("/admin/approvals", json("POST", { policy_id, proposed_content, reason, agent_id })),
  decide: (id: number, action: "approve" | "reject", content?: string) =>
    call<Approval>(`/admin/approvals/${id}/${action}`, json("POST", { content })),
  policies: () => call<Policy[]>("/policies"),
};
