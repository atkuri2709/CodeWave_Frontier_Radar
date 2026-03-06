const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

async function fetchApi<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options?.headers },
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export interface Run {
  id: number;
  pipeline_name: string | null;
  pipeline_description: string | null;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  trigger: string;
  agent_results: Record<string, { status: string; count?: number; error?: string; pages_processed?: number }> | null;
  findings_count: number;
  digest_id: number | null;
  error_message: string | null;
  created_at: string;
}

export interface PipelineConfig {
  id: number;
  pipeline_name: string;
  pipeline_description: string | null;
  config_json: Record<string, unknown> | null;
  enabled: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface Source {
  id: number;
  url: string;
  agent_id: string;
  name: string | null;
  rss_feed: string | null;
  rate_limit: number | null;
  include_rules: string[];
  exclude_rules: string[];
  enabled: boolean;
  created_at: string | null;
}

export interface FindingSummary {
  id: number;
  title: string;
  source_url: string;
  category: string;
  summary_short: string;
  confidence: number;
  agent_id: string;
  publisher: string | null;
  tags: string[];
  entities: string[];
  created_at: string;
}

export interface Digest {
  id: number;
  run_id: number;
  pdf_path: string | null;
  executive_summary: string | null;
  top_finding_ids: number[];
  recipients: string[];
  sent_at: string | null;
  created_at: string;
}

export interface ScheduledJob {
  id: number;
  pipeline_name: string;
  scheduler_name: string;
  frequency: 'daily' | 'weekly' | 'monthly' | 'yearly' | 'interval';
  run_time: string | null;
  timezone: string | null;
  start_date: string | null;
  end_date: string | null;
  start_time: string | null;
  end_time: string | null;
  interval_minutes: number | null;
  enabled: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface SchedulerStatus {
  running: boolean;
  job_count: number;
  jobs: { id: string; name: string; next_run?: string }[];
}

export interface LogEntry {
  id: number;
  run_id: number;
  timestamp: string;
  level: string;
  logger_name: string | null;
  message: string;
}

export interface AgentMeta {
  id: string;
  label: string;
  badge: string;
  color: string;
  description: string;
}

export interface CategoryMeta {
  id: string;
  label: string;
}

export interface AppMeta {
  agents: AgentMeta[];
  categories: CategoryMeta[];
}

export const api = {
  runs: {
    list: () => fetchApi<Run[]>('/runs/'),
    get: (id: number) => fetchApi<Run>(`/runs/${id}`),
    trigger: (opts: { trigger?: string; pipeline_name?: string; pipeline_description?: string; config_json?: Record<string, unknown>; save_config?: boolean; use_yaml?: boolean } = {}) =>
      fetchApi<Run>('/runs/', {
        method: 'POST',
        body: JSON.stringify({
          trigger: opts.trigger || 'manual',
          pipeline_name: opts.pipeline_name || null,
          pipeline_description: opts.pipeline_description || null,
          config_json: opts.config_json || null,
          save_config: opts.save_config || false,
          use_yaml: opts.use_yaml || false,
        }),
      }),
    pipelineNames: () => fetchApi<string[]>('/runs/pipeline-names'),
  },
  sources: {
    list: (agent_id?: string) => fetchApi<Source[]>(agent_id ? `/sources/?agent_id=${agent_id}` : '/sources/'),
    create: (body: Partial<Source> & { url: string; agent_id: string }) =>
      fetchApi<Source>('/sources/', { method: 'POST', body: JSON.stringify(body) }),
    get: (id: number) => fetchApi<Source>(`/sources/${id}`),
    update: (id: number, body: Partial<Source>) =>
      fetchApi<Source>(`/sources/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
    delete: (id: number) => fetch(`${API_BASE}/sources/${id}`, { method: 'DELETE' }),
  },
  findings: {
    list: (params?: { run_id?: number; agent_id?: string; category?: string }) => {
      const q = new URLSearchParams();
      if (params?.run_id) q.set('run_id', String(params.run_id));
      if (params?.agent_id) q.set('agent_id', params.agent_id);
      if (params?.category) q.set('category', params.category);
      return fetchApi<FindingSummary[]>(`/findings/?${q}`);
    },
  },
  digests: {
    list: () => fetchApi<Digest[]>('/digests/'),
    get: (id: number) => fetchApi<Digest>(`/digests/${id}`),
    downloadUrl: (id: number) => `${API_BASE}/digests/${id}/download`,
  },
  config: {
    get: () => fetchApi<Record<string, unknown>>('/config/'),
  },
  emailRecipients: {
    list: () => fetchApi<string[]>('/email-recipients'),
    update: (emails: string[]) =>
      fetchApi<string[]>('/email-recipients', { method: 'PUT', body: JSON.stringify(emails) }),
  },
  pipelineConfigs: {
    list: () => fetchApi<PipelineConfig[]>('/pipeline-configs/'),
    get: (id: number) => fetchApi<PipelineConfig>(`/pipeline-configs/${id}`),
    create: (body: { pipeline_name: string; pipeline_description?: string; config_json?: Record<string, unknown> }) =>
      fetchApi<PipelineConfig>('/pipeline-configs/', { method: 'POST', body: JSON.stringify(body) }),
    update: (id: number, body: Partial<PipelineConfig>) =>
      fetchApi<PipelineConfig>(`/pipeline-configs/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
    delete: (id: number) => fetchApi<{ ok: boolean }>(`/pipeline-configs/${id}`, { method: 'DELETE' }),
  },
  logs: {
    forRun: (runId: number) => fetchApi<LogEntry[]>(`/logs/${runId}`),
  },
  meta: {
    get: () => fetchApi<AppMeta>('/meta/'),
    agents: () => fetchApi<AgentMeta[]>('/meta/agents'),
    categories: () => fetchApi<CategoryMeta[]>('/meta/categories'),
  },
  scheduler: {
    list: () => fetchApi<ScheduledJob[]>('/scheduler/'),
    create: (body: Omit<ScheduledJob, 'id' | 'created_at' | 'updated_at'>) =>
      fetchApi<ScheduledJob>('/scheduler/', { method: 'POST', body: JSON.stringify(body) }),
    update: (id: number, body: Partial<ScheduledJob>) =>
      fetchApi<ScheduledJob>(`/scheduler/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
    delete: (id: number) => fetchApi<{ ok: boolean }>(`/scheduler/${id}`, { method: 'DELETE' }),
    status: () => fetchApi<SchedulerStatus>('/scheduler/status'),
    restart: () => fetchApi<SchedulerStatus>('/scheduler/restart', { method: 'POST' }),
  },
};
