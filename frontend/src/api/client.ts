const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export interface CatalogEntry {
  id: string;
  name: string;
  version: string;
  url: string;
  description: string;
}

export interface RuleSet {
  id: number;
  name: string;
  slug: string;
  source_type: "catalog" | "url" | "custom";
  source_url: string | null;
  version: string | null;
  order_seq: number;
  enabled: boolean;
  created_at: string;
  file_count: number;
  rule_count: number;
}

export interface RuleFile {
  id: number;
  rule_set_id: number;
  filename: string;
  file_kind: "setup" | "rule" | "asset";
  enabled: boolean;
  size_bytes: number;
  rule_count: number;
  created_at: string;
  updated_at: string;
}

export interface RuleRow {
  id: number;
  rule_file_id: number;
  rule_id: string | null;
  message: string | null;
  raw_snippet: string;
  enabled: boolean;
  order_index: number;
}

export interface CrsTuning {
  blocking_paranoia_level: number;
  detection_paranoia_level: number;
  inbound_anomaly_score_threshold: number;
  outbound_anomaly_score_threshold: number;
}

export interface TunableGroup {
  rule_id: string;
  description: string | null;
  is_active: boolean;
  variables: Record<string, string>;
}

export interface Site {
  id: number;
  name: string;
  domain: string;
  upstream_url: string;
  listen_port: number;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface LogSink {
  id: number;
  name: string;
  protocol: "udp" | "tcp";
  host: string;
  port: number;
  enabled: boolean;
  created_at: string;
}

export interface DiscordWebhook {
  id: number;
  name: string;
  webhook_url: string;
  enabled: boolean;
  created_at: string;
}

export interface ErrorPage {
  status_code: number;
  title: string;
  html_content: string;
  is_customized: boolean;
  updated_at: string | null;
}

export interface RuleMatch {
  rule_id: string | null;
  message: string | null;
  severity: string | null;
  tags: string[];
  data: string | null;
}

export interface AuditLogEntry {
  transaction_id: string;
  timestamp: string | null;
  client_ip: string | null;
  host: string | null;
  user_agent: string | null;
  method: string | null;
  uri: string | null;
  status_code: number | null;
  blocked: boolean;
  matches: RuleMatch[];
}

export interface AuditLogPage {
  total: number;
  limit: number;
  offset: number;
  items: AuditLogEntry[];
}

export interface StatsSummary {
  total_requests: number;
  total_blocked: number;
  total_detected: number;
  unique_ips: number;
}

export interface RuleCount {
  rule_id: string;
  message: string | null;
  count: number;
}

export interface IpCount {
  ip: string;
  count: number;
}

export interface TrendPoint {
  bucket: string;
  total: number;
  blocked: number;
}

export const TOKEN_STORAGE_KEY = "sentinel-waf-token";

// Set by AuthContext so a 401 anywhere can force a re-login without every
// call site having to handle it individually.
let onUnauthorized: (() => void) | null = null;
export function setUnauthorizedHandler(handler: () => void) {
  onUnauthorized = handler;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = localStorage.getItem(TOKEN_STORAGE_KEY);
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    ...init,
  });
  if (res.status === 401) {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
    onUnauthorized?.();
    throw new Error("401 Unauthorized");
  }
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export type Role = "admin" | "operator" | "viewer";

export interface LoginResult {
  access_token: string;
  must_change_password: boolean;
  role: Role;
}

export interface Me {
  username: string;
  role: Role;
  must_change_password: boolean;
}

export const authApi = {
  login: (username: string, password: string) =>
    request<LoginResult>("/api/auth/login", { method: "POST", body: JSON.stringify({ username, password }) }),
  me: () => request<Me>("/api/auth/me"),
  changePassword: (current_password: string, new_password: string) =>
    request<Me>("/api/auth/change-password", {
      method: "POST",
      body: JSON.stringify({ current_password, new_password }),
    }),
};

export interface TeamUser {
  id: number;
  username: string;
  role: Role;
  must_change_password: boolean;
  created_at: string;
}

export const usersApi = {
  list: () => request<TeamUser[]>("/api/users"),
  create: (username: string, password: string, role: Role) =>
    request<TeamUser>("/api/users", { method: "POST", body: JSON.stringify({ username, password, role }) }),
  updateRole: (id: number, role: Role) =>
    request<TeamUser>(`/api/users/${id}/role`, { method: "PATCH", body: JSON.stringify({ role }) }),
  resetPassword: (id: number) =>
    request<{ username: string; new_password: string }>(`/api/users/${id}/reset-password`, { method: "POST" }),
  delete: (id: number) => request<void>(`/api/users/${id}`, { method: "DELETE" }),
};

export interface EngineSettings {
  audit_engine: "On" | "Off" | "RelevantOnly";
  audit_log_relevant_status: string;
  request_body_access: boolean;
  response_body_access: boolean;
  request_body_limit: number;
  response_body_limit: number;
  response_body_mime_type: string;
  advanced_config: string;
  updated_at: string | null;
}

export const engineSettingsApi = {
  get: () => request<EngineSettings>("/api/engine-settings"),
  update: (payload: Omit<EngineSettings, "updated_at">) =>
    request<EngineSettings>("/api/engine-settings", { method: "PUT", body: JSON.stringify(payload) }),
};

export const discordApi = {
  list: () => request<DiscordWebhook[]>("/api/discord-webhooks"),
  create: (name: string, webhook_url: string) =>
    request<DiscordWebhook>("/api/discord-webhooks", { method: "POST", body: JSON.stringify({ name, webhook_url }) }),
  toggle: (id: number, enabled: boolean) =>
    request<DiscordWebhook>(`/api/discord-webhooks/${id}`, { method: "PATCH", body: JSON.stringify({ enabled }) }),
  delete: (id: number) => request<void>(`/api/discord-webhooks/${id}`, { method: "DELETE" }),
};

export const api = {
  // Rule sets / CRS catalog
  listCatalog: () => request<CatalogEntry[]>("/api/catalog"),
  listRuleSets: () => request<RuleSet[]>("/api/rule-sets"),
  importCatalog: (catalog_id: string) =>
    request<RuleSet>("/api/rule-sets/import-catalog", {
      method: "POST",
      body: JSON.stringify({ catalog_id }),
    }),
  importUrl: (name: string, url: string, version?: string) =>
    request<RuleSet>("/api/rule-sets/import-url", {
      method: "POST",
      body: JSON.stringify({ name, url, version }),
    }),
  toggleRuleSet: (id: number, enabled: boolean) =>
    request<RuleSet>(`/api/rule-sets/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ enabled }),
    }),
  deleteRuleSet: (id: number) => request<void>(`/api/rule-sets/${id}`, { method: "DELETE" }),
  listRuleFiles: (ruleSetId: number) => request<RuleFile[]>(`/api/rule-sets/${ruleSetId}/files`),

  // Rule files
  createRuleFile: (filename: string, content: string) =>
    request<RuleFile>("/api/rule-files", {
      method: "POST",
      body: JSON.stringify({ filename, content }),
    }),
  readRuleFile: (id: number) =>
    request<{ id: number; filename: string; content: string }>(`/api/rule-files/${id}`),
  updateRuleFile: (id: number, content: string) =>
    request<RuleFile>(`/api/rule-files/${id}`, {
      method: "PUT",
      body: JSON.stringify({ content }),
    }),
  toggleRuleFile: (id: number, enabled: boolean) =>
    request<RuleFile>(`/api/rule-files/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ enabled }),
    }),
  deleteRuleFile: (id: number) => request<void>(`/api/rule-files/${id}`, { method: "DELETE" }),

  // Individual rules
  listRules: (params: { rule_file_id?: number; rule_set_id?: number; search?: string; limit?: number }) => {
    const query = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== "") query.set(key, String(value));
    }
    return request<RuleRow[]>(`/api/rules?${query.toString()}`);
  },
  toggleRule: (id: number, enabled: boolean) =>
    request<RuleRow>(`/api/rules/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ enabled }),
    }),

  // CRS tuning (paranoia level / anomaly thresholds) - only present if the
  // rule set has a "setup" file (e.g. crs-setup.conf).
  getTuning: (ruleSetId: number) => request<CrsTuning>(`/api/rule-sets/${ruleSetId}/tuning`),
  updateTuning: (ruleSetId: number, tuning: CrsTuning) =>
    request<CrsTuning>(`/api/rule-sets/${ruleSetId}/tuning`, { method: "PUT", body: JSON.stringify(tuning) }),

  // Generic auto-detected tunables (any setvar:tx.X=Y block in the setup
  // file, beyond the 4 covered by getTuning/updateTuning above).
  listTunables: (ruleSetId: number) => request<TunableGroup[]>(`/api/rule-sets/${ruleSetId}/tunables`),
  updateTunable: (ruleSetId: number, ruleId: string, is_active: boolean, variables: Record<string, string>) =>
    request<TunableGroup>(`/api/rule-sets/${ruleSetId}/tunables/${ruleId}`, {
      method: "PUT",
      body: JSON.stringify({ is_active, variables }),
    }),

  // Sites (reverse proxy)
  listSites: () => request<Site[]>("/api/sites"),
  createSite: (site: Omit<Site, "id" | "enabled" | "created_at" | "updated_at">) =>
    request<Site>("/api/sites", { method: "POST", body: JSON.stringify(site) }),
  updateSite: (id: number, site: Omit<Site, "id" | "enabled" | "created_at" | "updated_at">) =>
    request<Site>(`/api/sites/${id}`, { method: "PUT", body: JSON.stringify(site) }),
  toggleSite: (id: number, enabled: boolean) =>
    request<Site>(`/api/sites/${id}`, { method: "PATCH", body: JSON.stringify({ enabled }) }),
  deleteSite: (id: number) => request<void>(`/api/sites/${id}`, { method: "DELETE" }),

  // Log sinks
  listLogSinks: () => request<LogSink[]>("/api/log-sinks"),
  createLogSink: (sink: Omit<LogSink, "id" | "enabled" | "created_at">) =>
    request<LogSink>("/api/log-sinks", { method: "POST", body: JSON.stringify(sink) }),
  toggleLogSink: (id: number, enabled: boolean) =>
    request<LogSink>(`/api/log-sinks/${id}`, { method: "PATCH", body: JSON.stringify({ enabled }) }),
  deleteLogSink: (id: number) => request<void>(`/api/log-sinks/${id}`, { method: "DELETE" }),

  // Error pages
  listErrorPages: () => request<ErrorPage[]>("/api/error-pages"),
  updateErrorPage: (statusCode: number, html_content: string) =>
    request<ErrorPage>(`/api/error-pages/${statusCode}`, {
      method: "PUT",
      body: JSON.stringify({ html_content }),
    }),
  resetErrorPage: (statusCode: number) =>
    request<ErrorPage>(`/api/error-pages/${statusCode}/reset`, { method: "POST" }),

  // Logs & stats (unchanged)
  listLogs: (params: Record<string, string | number | boolean | undefined>) => {
    const query = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== "") query.set(key, String(value));
    }
    return request<AuditLogPage>(`/api/logs?${query.toString()}`);
  },
  statsSummary: () => request<StatsSummary>("/api/stats/summary"),
  statsTopRules: (limit = 10) => request<RuleCount[]>(`/api/stats/top-rules?limit=${limit}`),
  statsTopIps: (limit = 10) => request<IpCount[]>(`/api/stats/top-ips?limit=${limit}`),
  statsTrend: () => request<TrendPoint[]>("/api/stats/trend"),
};
