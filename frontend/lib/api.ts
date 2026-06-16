const API_BASE = "/api/nim";

export interface APIKey {
  id: string;
  name: string;
  masked_key: string;
  is_active: boolean;
  is_default: boolean;
  usage_total_tokens: number;
  usage_total_requests: number;
  last_used_at: string | null;
  created_at: string;
}

export interface SummarizeRequest {
  table_text: string;
  model?: string;
  max_tokens?: number;
  temperature?: number;
}

export interface SummarizeResponse {
  summary: string;
  model_used: string;
  verified: boolean;
  numeric_accuracy: number;
  inference_time_ms: number;
  warnings: string[];
  tokens_generated: number | null;
  extracted_facts: Record<string, unknown>[];
}

export interface CSRTaskResponse {
  task_id: string;
  status: string;
  message: string;
}

export interface CSRProgress {
  status: string;
  stage: string;
  progress: number;
  current: number;
  total: number;
  message: string;
  elapsed_seconds: number;
  eta_seconds: number;
  result?: Record<string, unknown>;
  error?: string;
}

export interface HealthResponse {
  status: string;
  version: string;
  active_keys: number;
  total_keys: number;
  default_model: string;
}

async function fetchJson<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      ...(options?.headers || {}),
    },
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error((data as { detail?: string }).detail || res.statusText);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => fetchJson<HealthResponse>("/health"),

  listKeys: () => fetchJson<{ keys: APIKey[] }>("/keys"),
  createKey: (data: { name: string; key: string; is_default?: boolean }) =>
    fetchJson<APIKey>("/keys", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),
  updateKey: (id: string, data: Partial<APIKey>) =>
    fetchJson<APIKey>(`/keys/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),
  deleteKey: (id: string) =>
    fetchJson<{ status: string; id: string }>(`/keys/${id}`, { method: "DELETE" }),
  getKeyUsage: (id: string, days?: number) =>
    fetchJson<{ aggregates: Record<string, number>; events: unknown[] }>(
      `/keys/${id}/usage${days ? `?days=${days}` : ""}`
    ),

  summarize: (data: SummarizeRequest) =>
    fetchJson<SummarizeResponse>("/summarize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),

  startCSR: (file: File, options?: { model?: string; max_workers?: number; max_tokens?: number }) => {
    const form = new FormData();
    form.append("file", file);
    if (options?.model) form.append("model", options.model);
    if (options?.max_workers) form.append("max_workers", String(options.max_workers));
    if (options?.max_tokens) form.append("max_tokens", String(options.max_tokens));
    return fetchJson<CSRTaskResponse>("/csr", { method: "POST", body: form });
  },

  getCSRProgress: (taskId: string) =>
    fetchJson<CSRProgress>(`/csr/progress/${taskId}`),

  downloadCSRDocx: (token: string) =>
    fetch(`${API_BASE}/csr/download/${token}`),

  downloadCSRQcReport: (token: string) =>
    fetch(`${API_BASE}/csr/download/${token}/qc`),

  downloadCSRAuditLog: (token: string) =>
    fetch(`${API_BASE}/csr/download/${token}/audit`),
};
