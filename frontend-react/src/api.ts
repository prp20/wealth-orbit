const base = import.meta.env.VITE_API_BASE_URL || '/api/v1';

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${base}${path}`);
  if (!response.ok) {
    throw new Error((await response.json().catch(() => ({}))).detail || 'Could not load data');
  }
  return response.json();
}

async function post<T>(path: string): Promise<T> {
  const response = await fetch(`${base}${path}`, { method: 'POST' });
  if (!response.ok) {
    throw new Error((await response.json().catch(() => ({}))).detail || 'Sync failed');
  }
  return response.json();
}

export type SyncJob = {
  job_id: string;
  status: string;
  progress_percent?: number;
  last_error?: string | null;
  result?: string | Record<string, unknown> | null;
  completed_at?: string | null;
  started_at?: string | null;
  queued_at?: string | null;
  duplicate?: boolean;
};

export function syncJobFailureMessage(job: SyncJob | null | undefined): string | null {
  if (!job) return null;
  if (String(job.status || '').toUpperCase() === 'FAILED') {
    return job.last_error || 'Sync failed';
  }
  let result = job.result;
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
    if ((result as any).fundamental_rows === 0 && (result as any).shareholding_rows === 0) {
      return 'Sync completed with no fundamental rows';
    }
  }
  return null;
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

export const api = {
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
  stockCompare: (symbols: string[]) =>
    get<any[]>(`/market-data/stocks/compare?symbols=${encodeURIComponent(symbols.join(','))}`),
  syncStock: (id: string, kind: string, force: boolean) =>
    post<SyncJob>(`/market-data/stocks/${encodeURIComponent(id)}/sync?kind=${kind}&force=${force}`),
  syncStockStatus: (id: string, kind: string) =>
    get<{ status: string; kind: string; job: SyncJob | null }>(
      `/market-data/stocks/${encodeURIComponent(id)}/sync/status?kind=${kind}`,
    ),
  syncJob: (jobId: string) => get<SyncJob>(`/market-data/sync/jobs/${encodeURIComponent(jobId)}`),
  syncFund: (id: string, force: boolean) =>
    post<SyncJob>(`/market-data/mutual-funds/${encodeURIComponent(id)}/sync?kind=nav&force=${force}`),
  syncFundKind: (id: string, kind: string, force: boolean) =>
    post<SyncJob>(
      `/market-data/mutual-funds/${encodeURIComponent(id)}/sync/${encodeURIComponent(kind)}?force=${force}`,
    ),
  syncFundStatus: (id: string, kind: string) =>
    get<{ status: string; kind: string; job: SyncJob | null }>(
      `/market-data/mutual-funds/${encodeURIComponent(id)}/sync/status?kind=${encodeURIComponent(kind)}`,
    ),
  fundBenchmark: (id: string) => get<any>(`/market-data/mutual-funds/${encodeURIComponent(id)}/benchmark`),
  fundBenchmarkHistory: (id: string, from = '', to = '') =>
    get<any[]>(
      withDates(`/market-data/mutual-funds/${encodeURIComponent(id)}/benchmark/history`, from, to),
    ),
  sectors: () => get<string[]>('/market-data/sectors'),
  filters: (kind: string) => get<string[]>(`/market-data/filters/${kind}`),
};
