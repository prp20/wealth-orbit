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

export function syncJobFailureMessage(job: SyncJob | SyncJobByKind | null | undefined): string | null {
  if (!job) return null;
  if (String(job.status || '').toUpperCase() === 'FAILED') {
    return job.last_error || 'Sync failed';
  }
  let result = 'result' in job ? job.result : undefined;
  if (typeof result === 'string') {
    try {
      result = JSON.parse(result);
    } catch {
      result = null;
    }
  }
  if (result && typeof result === 'object') {
    const status = String((result as any).status || '').toLowerCase();
    if (status === 'failed' || status === 'error') {
      return String((result as any).reason || (result as any).error || 'Sync failed');
    }
  }
  return null;
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
    get<any[]>(
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
  benchmarkSummary: (codes: string[]) =>
    get<any[]>(`/market-data/benchmarks/summary?codes=${encodeURIComponent(codes.join(','))}`),
  syncBenchmarks: (codes: string[], historyPeriod = '') => {
    const params = new URLSearchParams({ codes: codes.join(',') });
    if (historyPeriod) params.set('history_period', historyPeriod);
    return post<SyncJob>(`/market-data/benchmarks/sync?${params}`);
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
  trackStockInstrument: (tradingSymbol: string, enqueueHistory = true, historyPeriod = '5y') => {
    const params = new URLSearchParams({
      enqueue_history: enqueueHistory ? 'true' : 'false',
      history_period: historyPeriod,
    });
    return postJson<TrackInstrumentResult>(`/market-data/instruments/stocks?${params}`, {
      trading_symbol: tradingSymbol,
    });
  },
  trackFundInstrument: (schemeCode: string, enqueueHistory = true, historyPeriod = '5y') => {
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
    historyPeriod = '5y',
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
  sectors: () => get<string[]>('/market-data/sectors'),
  filters: (kind: string) => get<string[]>(`/market-data/filters/${kind}`),
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
  status: 'created' | 'existing';
  already_tracked: boolean;
  master: Record<string, unknown>;
  jobs: { job_id?: string; kind?: string; duplicate?: boolean }[];
  preview?: InstrumentPreview;
};
