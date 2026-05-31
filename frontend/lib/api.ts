/**
 * Scan-service HTTP client. Single typed wrapper used by every page.
 */

const BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return res.json();
}

// ===== Types =====

export type Span = {
  start: number;
  end: number;
  label: string;
  value: string;
  score: number;
  detector: string;
};

export type ScanResponse = {
  file_id: string;
  source_path: string | null;
  content_hash: string | null;
  chars: number;
  spans: Span[];
  deduped: boolean;
  timing_ms: Record<string, number>;
  tiers_used: string[];
};

export type CompareResponse = {
  text: string;
  results: Record<string, Span[]>;
  timing_ms: Record<string, number>;
};

export type Finding = {
  id: number;
  file_path: string;
  label: string;
  value: string;
  score: number;
  severity: "low" | "medium" | "high" | "critical";
  owner: string | null;
  detector: string;
  created_at: string;
};

export type Summary = {
  files_with_findings: number;
  total_findings: number;
  by_severity: Record<string, number>;
  by_label: Record<string, number>;
  by_detector: Record<string, number>;
  top_exposed_owners: { owner: string; count: number }[];
};

export type Agent = {
  id: string;
  name: string;
  version: string;
  domain: string;
  description: string;
  tools: string[];
  inputs: string[];
  outputs: string[];
  endorsements: number;
};

export type PersonIdentity = {
  query: string;
  canonical: string;
  display_name: string;
  files: string[];
  file_count: number;
  identifiers: Record<string, string[]>;
  fuzzy_matches: { canonical: string; value: string; similarity: number }[];
  re_id_risk: "low" | "medium" | "high" | "critical";
  risk_factors: string[];
};

export type MosaicGraph = {
  nodes: { id: string; label: string; value: string; docs: number }[];
  edges: { source: string; target: string; file: string }[];
};

export type DSARMatch = {
  file_path: string;
  matched_terms: string[];
  confidence: number;
  proposed_action: "delete" | "anonymize" | "redact" | "retain";
  reason: string;
};

export type DSARPlan = {
  subject: string;
  article: string;
  matches: DSARMatch[];
  summary: string;
  risk_notes: string[];
};

// ===== API =====

export const api = {
  health: () => http<{ ok: boolean; service: string; version: string }>("/health"),

  scanFile: (path: string) =>
    http<ScanResponse>("/scan/file", { method: "POST", body: JSON.stringify({ path }) }),

  scanText: (text: string) =>
    http<ScanResponse>("/scan/file", { method: "POST", body: JSON.stringify({ text }) }),

  scanAll: (text: string, models?: string[]) =>
    http<CompareResponse>("/scan/all", {
      method: "POST",
      body: JSON.stringify({ text, models }),
    }),

  findings: (params?: { owner?: string; label?: string; limit?: number }) => {
    const q = new URLSearchParams();
    if (params?.owner) q.set("owner", params.owner);
    if (params?.label) q.set("label", params.label);
    if (params?.limit) q.set("limit", String(params.limit));
    return http<Finding[]>(`/findings?${q.toString()}`);
  },

  summary: () => http<Summary>("/findings/summary"),

  agents: () => http<Agent[]>("/agents"),
  endorseAgent: (id: string) =>
    http<Agent>(`/agents/${id}/endorse`, { method: "POST" }),

  person: (q: string) =>
    http<PersonIdentity>(`/mosaic/person?q=${encodeURIComponent(q)}`),

  graph: (limitPeople = 50) =>
    http<MosaicGraph>(`/mosaic/graph?limit_people=${limitPeople}`),

  suggestions: (limit = 8) =>
    http<{ name: string; docs: number }[]>(`/mosaic/suggestions?limit=${limit}`),

  dsarPlan: (subject: string, article: "17" | "5" | "32" = "17") =>
    http<DSARPlan>("/dsar/plan", {
      method: "POST",
      body: JSON.stringify({ subject, article }),
    }),

  dsarExecute: (subject: string, article: "17" | "5" | "32" = "17") =>
    http<{ subject: string; article: string; files_processed: number; findings_erased: number; certificate_url: string }>(
      "/dsar/execute",
      { method: "POST", body: JSON.stringify({ subject, article }) },
    ),

  /** SSE — returns an EventSource you must close yourself. */
  scanStreamEventSource(source: "filesystem" | "sharepoint" = "sharepoint"): EventSource {
    return new EventSource(`${BASE}/scan/stream?source=${source}`);
  },
};

export { BASE };
