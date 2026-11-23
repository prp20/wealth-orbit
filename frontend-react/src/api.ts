const base = import.meta.env.VITE_API_BASE_URL || '/api/v1';

function errorDetail(payload: any, fallback: string) {
  const detail = payload?.detail;
  if (typeof detail === 'string') return detail;
  if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
    const message = detail.message || detail.reason;
    if (typeof message === 'string' && message.trim()) return message;
  }
  if (Array.isArray(detail) && detail.length) return 'Use at least 8 characters.';
  return fallback;
}

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${base}${path}`, { credentials: 'include' });
  if (!response.ok) {
    throw new Error(errorDetail(await response.json().catch(() => ({})), 'Could not load data'));
  }
  return response.json();
}

async function post<T>(path: string): Promise<T> {
  const response = await fetch(`${base}${path}`, { method: 'POST', credentials: 'include' });
  if (!response.ok) {
    throw new Error(errorDetail(await response.json().catch(() => ({})), 'Sync failed'));
  }
  return response.json();
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${base}${path}`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(errorDetail(await response.json().catch(() => ({})), 'Could not sign in'));
  }
  return response.json();
}

async function patchJson<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${base}${path}`, {
    method: 'PATCH',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(errorDetail(await response.json().catch(() => ({})), 'Could not update'));
  }
  return response.json();
}

export type SyncJob = {
  job_id: string;
  status: string;
  entity_type?: string;
  entity_key?: string;
  sync_type?: string;
  progress_percent?: number;
  last_error?: string | null;
  result?: string | Record<string, unknown> | null;
  completed_at?: string | null;
  started_at?: string | null;
  queued_at?: string | null;
  duplicate?: boolean;
};

export type SyncJobByKind = {
  job_id?: string;
  status?: string;
  last_error?: string | null;
  completed_at?: string | null;
  started_at?: string | null;
  queued_at?: string | null;
  progress_percent?: number | null;
};

export type StockTechnicalIndicatorsPayload = {
  records: any[];
  sync_error?: string | null;
  stored_only?: boolean;
};

function parseJobResult(job: SyncJob | SyncJobByKind | null | undefined): Record<string, unknown> | null {
  if (!job || !('result' in job)) return null;
  let result = job.result;
  if (typeof result === 'string') {
    try {
      result = JSON.parse(result);
    } catch {
      return null;
    }
  }
  if (!result || typeof result !== 'object') return null;
  return result as Record<string, unknown>;
}

export function syncJobFailureMessage(job: SyncJob | SyncJobByKind | null | undefined): string | null {
  if (!job) return null;
  if (String(job.status || '').toUpperCase() === 'FAILED') {
    return job.last_error || 'Sync failed';
  }
  const result = parseJobResult(job);
  if (result) {
    const status = String(result.status || '').toLowerCase();
    if (status === 'failed' || status === 'error') {
      return String(result.reason || result.error || 'Sync failed');
    }
  }
  return null;
}

/** SUCCEEDED jobs that still report per-item failures (e.g. index sync). */
export function syncJobPartialFailureMessage(
  job: SyncJob | SyncJobByKind | null | undefined,
  limit = 4,
): string | null {
  if (!job || String(job.status || '').toUpperCase() === 'FAILED') return null;
  const result = parseJobResult(job);
  const failed = result?.failed;
  if (!Array.isArray(failed) || !failed.length) return null;
  const parts = failed
    .slice(0, limit)
    .map((item) => {
      if (!item || typeof item !== 'object') return null;
      const row = item as { index_code?: string; reason?: string };
      const code = String(row.index_code || '').trim();
      const reason = String(row.reason || 'failed').trim();
      return code ? `${code}: ${reason}` : reason;
    })
    .filter(Boolean) as string[];
  if (!parts.length) return null;
  const extra = failed.length > limit ? ` · +${failed.length - limit} more` : '';
  const text = parts.join('; ') + extra;
  return text.length > 220 ? `${text.slice(0, 217)}…` : text;
}

export function failedSyncSummaries(
  lastSyncByKind: Record<string, SyncJobByKind | null | undefined> | null | undefined,
  limit = 3,
): { kind: string; reason: string }[] {
  if (!lastSyncByKind) return [];
  const rows: { kind: string; reason: string }[] = [];
  for (const [kind, job] of Object.entries(lastSyncByKind)) {
    const reason = syncJobFailureMessage(job);
    if (!reason) continue;
    rows.push({ kind, reason: reason.length > 80 ? `${reason.slice(0, 77)}…` : reason });
    if (rows.length >= limit) break;
  }
  return rows;
}

export function syncQueueQuery(includeHistory = true, limit = 12): string {
  return `include_history=${includeHistory ? 'true' : 'false'}&limit=${limit}`;
}

export function formatSyncJobLabel(job: {
  entity_type?: string;
  entity_key?: string;
  sync_type?: string;
}): string {
  const entity = [job.entity_type, job.entity_key].filter(Boolean).join(' ');
  const kind = job.sync_type || 'sync';
  return entity ? `${entity} · ${kind}` : kind;
}

export type InsightItem = {
  id: string;
  kind: string;
  title: string;
  body: string;
  citations?: string[];
  created_at?: string;
};

function withDates(path: string, from = '', to = '') {
  const params = new URLSearchParams();
  if (from) params.set('from_date', from);
  if (to) params.set('to_date', to);
  const query = params.toString();
  return query ? `${path}?${query}` : path;
}

export type LocalAccount = {
  signed_in: boolean;
  full_name: string | null;
  portfolio_id: string | null;
};

export const api = {
  authStatus: () => get<{ password_set: boolean }>('/auth/status'),
  authMe: () => get<LocalAccount>('/auth/me'),
  authSignup: (fullName: string, password: string) =>
    postJson<LocalAccount>('/auth/signup', { full_name: fullName, password }),
  authLogin: (fullName: string, password: string) =>
    postJson<LocalAccount>('/auth/login', { full_name: fullName, password }),
  authLogout: () => post<{ ok: boolean }>('/auth/logout'),
  portfolios: () => get<any[]>('/portfolios'),
  holdings: (id: string) => get<any[]>(`/portfolios/${id}/holdings`),
  transactions: (id: string, from = '', to = '', type = '') => {
    const params = new URLSearchParams();
    if (from) params.set('from_date', from);
    if (to) params.set('to_date', to);
    if (type) params.set('transaction_type', type);
    const query = params.toString();
    return get<any[]>(`/portfolios/${id}/transactions${query ? `?${query}` : ''}`);
  },
  funds: (params: string) => get<any[]>(`/market-data/mutual-funds?${params}`),
  fund: (id: string) => get<any>(`/market-data/mutual-funds/${encodeURIComponent(id)}`),
  fundByName: (id: string) => get<any>(`/market-data/mutual-funds/by-name/${encodeURIComponent(id)}`),
  fundHistory: (id: string, from = '', to = '') =>
    get<any[]>(withDates(`/market-data/mutual-funds/${encodeURIComponent(id)}/history`, from, to)),
  fundMetrics: (id: string) => get<any>(`/market-data/mutual-funds/${encodeURIComponent(id)}/metrics`),
  fundEnrichment: (id: string) => get<any[]>(`/market-data/mutual-funds/${encodeURIComponent(id)}/enrichment`),
  fundSimilar: (id: string) => get<any[]>(`/market-data/mutual-funds/${encodeURIComponent(id)}/similar`),
  fundScreen: (params: string) =>
    get<{ metric_period: string; total: number; limit: number; offset: number; rows: any[] }>(
      `/market-data/mutual-funds/screen?${params}`,
    ),
  fundCompare: (codes: string[], metricPeriod = '1Y') =>
    get<any[]>(
      `/market-data/mutual-funds/compare?scheme_codes=${encodeURIComponent(codes.join(','))}&metric_period=${encodeURIComponent(metricPeriod)}`,
    ),
  fundHoldings: (id: string, topN = 20) =>
    get<any>(`/market-data/mutual-funds/${encodeURIComponent(id)}/holdings?top_n=${topN}`),
  fundManagers: (id: string) => get<any>(`/market-data/mutual-funds/${encodeURIComponent(id)}/managers`),
  fundOverlap: (codes: string[]) =>
    get<any>(
      `/market-data/mutual-funds/overlap?scheme_codes=${encodeURIComponent(codes.join(','))}`,
    ),
  stocks: (params: string) => get<any[]>(`/market-data/stocks?${params}`),
  stockScreen: (params: string) =>
    get<{
      rows: any[];
      total: number;
      limit: number;
      offset: number;
      snapshot_size: number;
      metrics_available: number;
      columns: string[];
    }>(`/market-data/stocks/screen?${params}`),
  stockScreens: (runnableOnly = false) =>
    get<{ asset_class: string; timeout_seconds: number; screens: any[] }>(
      `/market-data/stocks/screens?runnable_only=${runnableOnly ? 'true' : 'false'}`,
    ),
  refreshStockScreens: () =>
    postJson<{ asset_class: string; timeout_seconds: number; screens: any[]; refreshed: boolean }>(
      '/market-data/stocks/screens/refresh',
      {},
    ),
  runStockScreen: (screenId: string, params: Record<string, unknown> = {}) =>
    postJson<{
      ok: boolean;
      screen_id: string;
      name?: string;
      params: Record<string, unknown>;
      rows: any[];
      symbols: string[];
      total: number;
      error?: string | null;
    }>(`/market-data/stocks/screens/${encodeURIComponent(screenId)}/run`, { params }),
  stock: (id: string) => get<any>(`/market-data/stocks/${encodeURIComponent(id)}`),
  stockHistory: (id: string, from = '', to = '') =>
    get<any[]>(withDates(`/market-data/stocks/${encodeURIComponent(id)}/history`, from, to)),
  stockMetrics: (id: string) => get<any[]>(`/market-data/stocks/${encodeURIComponent(id)}/metrics/daily`),
  stockFundamentals: (id: string, params = '') =>
    get<any[]>(`/market-data/stocks/${encodeURIComponent(id)}/fundamentals${params ? `?${params}` : ''}`),
  stockFundamentalsSummary: (id: string, period = 'ANNUAL', basis = 'CONSOLIDATED') => {
    const params = new URLSearchParams({ reporting_period: period, reporting_basis: basis });
    return get<any>(`/market-data/stocks/${encodeURIComponent(id)}/fundamentals/summary?${params}`);
  },
  stockShareholding: (id: string) => get<any[]>(`/market-data/stocks/${encodeURIComponent(id)}/shareholding`),
  stockTechnical: (id: string, indicator = '') =>
    get<StockTechnicalIndicatorsPayload>(
      `/market-data/stocks/${encodeURIComponent(id)}/technical-indicators${
        indicator ? `?indicator=${encodeURIComponent(indicator)}` : ''
      }`,
    ),
  stockPeers: (id: string, by = 'sector', limit = 8) =>
    get<any>(`/market-data/stocks/${encodeURIComponent(id)}/peers?by=${encodeURIComponent(by)}&limit=${limit}`),
  stockValuation: (id: string) => get<any>(`/market-data/stocks/${encodeURIComponent(id)}/valuation`),
  stockCompare: (symbols: string[]) =>
    get<any[]>(`/market-data/stocks/compare?symbols=${encodeURIComponent(symbols.join(','))}`),
  syncStock: (id: string, kind: string, force: boolean, historyPeriod = '') => {
    const params = new URLSearchParams({ kind, force: String(force) });
    if (historyPeriod) params.set('history_period', historyPeriod);
    return post<SyncJob>(`/market-data/stocks/${encodeURIComponent(id)}/sync?${params}`);
  },
  syncStockStatus: (id: string, kind: string) =>
    get<{ status: string; kind: string; job: SyncJob | null }>(
      `/market-data/stocks/${encodeURIComponent(id)}/sync/status?kind=${kind}`,
    ),
  syncJob: (jobId: string) => get<SyncJob>(`/market-data/sync/jobs/${encodeURIComponent(jobId)}`),
  syncQueue: (includeHistory = true, limit = 12) =>
    get<{ jobs: SyncJob[] }>(`/market-data/sync/queue?${syncQueueQuery(includeHistory, limit)}`),
  syncFund: (id: string, force: boolean, historyPeriod = '') => {
    const params = new URLSearchParams({ kind: 'nav', force: String(force) });
    if (historyPeriod) params.set('history_period', historyPeriod);
    return post<SyncJob>(`/market-data/mutual-funds/${encodeURIComponent(id)}/sync?${params}`);
  },
  syncFundKind: (id: string, kind: string, force: boolean, historyPeriod = '') => {
    const params = new URLSearchParams({ force: String(force) });
    if (historyPeriod) params.set('history_period', historyPeriod);
    return post<SyncJob>(
      `/market-data/mutual-funds/${encodeURIComponent(id)}/sync/${encodeURIComponent(kind)}?${params}`,
    );
  },
  syncFundStatus: (id: string, kind: string) =>
    get<{ status: string; kind: string; job: SyncJob | null }>(
      `/market-data/mutual-funds/${encodeURIComponent(id)}/sync/status?kind=${encodeURIComponent(kind)}`,
    ),
  fundBenchmark: (id: string) => get<any>(`/market-data/mutual-funds/${encodeURIComponent(id)}/benchmark`),
  fundBenchmarkHistory: (id: string, from = '', to = '') =>
    get<any[]>(
      withDates(`/market-data/mutual-funds/${encodeURIComponent(id)}/benchmark/history`, from, to),
    ),
  usdInrRate: () =>
    get<{ base: string; quote: string; rate: number; as_of?: string | number | null; provider?: string }>(
      '/market-data/fx/usd-inr',
    ),
  benchmarks: () => get<{ index_id?: string; index_code: string; index_name?: string }[]>('/market-data/benchmarks'),
  benchmarkSummary: (codes?: string[]) => {
    if (!codes?.length) return get<any[]>('/market-data/benchmarks/summary');
    return get<any[]>(`/market-data/benchmarks/summary?codes=${encodeURIComponent(codes.join(','))}`);
  },
  syncBenchmarks: (codes?: string[], historyPeriod = '') => {
    const params = new URLSearchParams();
    if (codes?.length) params.set('codes', codes.join(','));
    if (historyPeriod) params.set('history_period', historyPeriod);
    const qs = params.toString();
    return post<SyncJob>(`/market-data/benchmarks/sync${qs ? `?${qs}` : ''}`);
  },
  syncBenchmarkStatus: () =>
    get<{ status: string; job: SyncJob | null }>('/market-data/benchmarks/sync/status'),
  previewStockInstrument: (tradingSymbol: string) =>
    get<InstrumentPreview>(
      `/market-data/instruments/stocks/preview?trading_symbol=${encodeURIComponent(tradingSymbol)}`,
    ),
  previewFundInstrument: (schemeCode: string) =>
    get<InstrumentPreview>(
      `/market-data/instruments/mutual-funds/preview?scheme_code=${encodeURIComponent(schemeCode)}`,
    ),
  previewIndexInstrument: (indexCode: string, yfSymbol = '') => {
    const params = new URLSearchParams({ index_code: indexCode });
    if (yfSymbol) params.set('yf_symbol', yfSymbol);
    return get<InstrumentPreview>(`/market-data/instruments/indexes/preview?${params}`);
  },
  trackStockInstrument: (tradingSymbol: string, enqueueHistory = true, historyPeriod = '10y') => {
    const params = new URLSearchParams({
      enqueue_history: enqueueHistory ? 'true' : 'false',
      history_period: historyPeriod,
    });
    return postJson<TrackInstrumentResult>(`/market-data/instruments/stocks?${params}`, {
      trading_symbol: tradingSymbol,
    });
  },
  trackFundInstrument: (schemeCode: string, enqueueHistory = true, historyPeriod = '10y') => {
    const params = new URLSearchParams({
      enqueue_history: enqueueHistory ? 'true' : 'false',
      history_period: historyPeriod,
    });
    return postJson<TrackInstrumentResult>(`/market-data/instruments/mutual-funds?${params}`, {
      scheme_code: schemeCode,
    });
  },
  trackIndexInstrument: (
    indexCode: string,
    yfSymbol = '',
    enqueueHistory = true,
    historyPeriod = '10y',
  ) => {
    const params = new URLSearchParams({
      enqueue_history: enqueueHistory ? 'true' : 'false',
      history_period: historyPeriod,
    });
    return postJson<TrackInstrumentResult>(`/market-data/instruments/indexes?${params}`, {
      index_code: indexCode,
      yf_symbol: yfSymbol || null,
    });
  },
  updateIndexInstrument: (
    indexCode: string,
    yfSymbol: string,
    enqueueHistory = true,
    historyPeriod = '10y',
  ) => {
    const params = new URLSearchParams({
      enqueue_history: enqueueHistory ? 'true' : 'false',
      history_period: historyPeriod,
    });
    return patchJson<TrackInstrumentResult>(
      `/market-data/instruments/indexes/${encodeURIComponent(indexCode)}?${params}`,
      { yf_symbol: yfSymbol },
    );
  },
  sectors: () => get<string[]>('/market-data/sectors'),
  filters: (kind: string) => get<string[]>(`/market-data/filters/${kind}`),
  vaultGet: () => get<VaultMeta>('/vault'),
  vaultPullSummary: () => get<VaultSummary>('/vault/pull-summary'),
  vaultPushFromSqlite: () => postJson<VaultPushResult>('/vault/push-from-sqlite', {}),
  vaultReset: (confirm: string) => postJson<VaultResetResult>('/vault/reset', { confirm }),
};

export type VaultMeta = {
  user_id: string;
  vault_generation: number;
  version: number;
  ciphertext: string;
  updated_at: string | null;
};

export type VaultSummary = {
  vault_generation: number;
  version: number;
  schema_version?: number;
  portfolio_id?: string;
  assets_count: number;
  holdings_count: number;
  transactions_count: number;
  exported_at?: string;
};

export type VaultPushResult = {
  ok: boolean;
  vault: VaultMeta;
  holdings_count: number;
  transactions_count: number;
};

export type VaultResetResult = {
  ok: boolean;
  vault_generation: number;
  version: number;
  message: string;
};

export type InstrumentPreview = {
  instrument_type: 'stock' | 'mutual_fund' | 'index';
  trading_symbol?: string;
  company_name?: string;
  exchange?: string;
  scheme_code?: string;
  scheme_name?: string;
  amc_name?: string;
  index_code?: string;
  index_name?: string;
  yf_symbol?: string;
};

export type TrackInstrumentResult = {
  status: 'created' | 'existing' | 'updated';
  already_tracked: boolean;
  master: Record<string, unknown>;
  jobs: { job_id?: string; kind?: string; duplicate?: boolean }[];
  preview?: InstrumentPreview;
};
