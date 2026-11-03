import React from 'react';
import { Link, NavLink, Navigate, Route, Routes, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api';
import MarketChart from '../components/MarketChart';
import StockListPage from '../pages/stocks/StockListPage';
import StockDetailPage from '../pages/stocks/StockDetailPage';

const money = (value: unknown) =>
  value == null
    ? '—'
    : `₹${new Intl.NumberFormat('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(value))}`;

function Page({ title, subtitle, children }: { title: string; subtitle: string; children?: React.ReactNode }) {
  return (
    <>
      <header>
        <p className="eyebrow">Wealth Orbit</p>
        <h1>{title}</h1>
        <p className="subtitle">{subtitle}</p>
      </header>
      {children}
    </>
  );
}

function LoadingOrError({ query }: { query: { isLoading: boolean; error: Error | null } }) {
  if (query.isLoading) return <div className="loading">Loading data…</div>;
  if (query.error) return <div className="empty">{query.error.message}</div>;
  return null;
}

function Table({ rows, linkKey, linkBase }: { rows: any[]; linkKey?: string; linkBase?: string }) {
  if (!rows.length) return <div className="empty">No data available yet.</div>;
  const keys = Object.keys(rows[0]);
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {keys.map((key) => (
              <th key={key}>{key.replaceAll('_', ' ')}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index}>
              {keys.map((key) => (
                <td key={key}>
                  {key === linkKey ? (
                    <Link to={`${linkBase}${encodeURIComponent(row[key])}`}>{String(row[key])}</Link>
                  ) : (
                    String(row[key] ?? '—')
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Shell() {
  const portfolios = useQuery({ queryKey: ['portfolios'], queryFn: api.portfolios });
  return (
    <div className="shell">
      <aside>
        <div className="brand">
          wealth<span>orbit</span>
          <small>Investment workspace</small>
        </div>
        <div className="owner">
          {portfolios.data?.[0]?.user_name || 'Portfolio owner'}
          <small>Personal portfolio</small>
        </div>
        <nav>
          <NavLink to="/portfolio">Portfolio</NavLink>
          <NavLink to="/transactions">Transactions</NavLink>
          <NavLink to="/mutualfunds">Mutual funds</NavLink>
          <NavLink to="/stocks">Stocks</NavLink>
        </nav>
      </aside>
      <main>
        <Routes>
          <Route path="/" element={<Navigate replace to="/portfolio" />} />
          <Route path="/portfolio" element={<PortfolioPage />} />
          <Route path="/transactions" element={<TransactionsPage />} />
          <Route path="/mutualfunds" element={<FundList />} />
          <Route path="/mutualfunds/:schemeId" element={<FundDetail />} />
          <Route path="/mutual-funds" element={<Navigate replace to="/mutualfunds" />} />
          <Route path="/mutual-funds/:schemeId" element={<FundDetail />} />
          <Route path="/stocks" element={<StockListPage />} />
          <Route path="/stocks/:symbol" element={<StockDetailPage />} />
          <Route path="*" element={<Navigate replace to="/portfolio" />} />
        </Routes>
      </main>
    </div>
  );
}

function PortfolioPage() {
  const portfolios = useQuery({ queryKey: ['portfolios'], queryFn: api.portfolios });
  const portfolioId = portfolios.data?.[0]?.portfolio_id;
  const holdings = useQuery({
    queryKey: ['holdings', portfolioId],
    queryFn: () => api.holdings(portfolioId),
    enabled: Boolean(portfolioId),
  });
  const invested = (holdings.data || []).reduce((sum, holding) => sum + Number(holding.invested_amount || 0), 0);
  return (
    <Page title="Portfolio overview" subtitle="Your positions, cost basis, and allocation at a glance.">
      <LoadingOrError query={portfolios} />
      <section className="metrics">
        <div className="metric">
          <small>Invested amount</small>
          <strong>{money(invested)}</strong>
        </div>
        <div className="metric">
          <small>Assets held</small>
          <strong>{holdings.data?.length || 0}</strong>
        </div>
      </section>
      <section className="panel">
        <h2>Current holdings</h2>
        <LoadingOrError query={holdings} />
        <Table rows={holdings.data || []} />
      </section>
    </Page>
  );
}

function TransactionsPage() {
  const portfolios = useQuery({ queryKey: ['portfolios'], queryFn: api.portfolios });
  const portfolioId = portfolios.data?.[0]?.portfolio_id;
  const transactions = useQuery({
    queryKey: ['transactions', portfolioId],
    queryFn: () => api.transactions(portfolioId),
    enabled: Boolean(portfolioId),
  });
  return (
    <Page title="Transactions" subtitle="Recorded portfolio purchases and redemptions.">
      <section className="panel">
        <LoadingOrError query={transactions} />
        <Table rows={transactions.data || []} />
      </section>
    </Page>
  );
}

function FundList() {
  const [query, setQuery] = React.useState('');
  const funds = useQuery({
    queryKey: ['funds', query],
    queryFn: () => api.funds(new URLSearchParams({ search: query }).toString()),
  });
  return (
    <Page title="Mutual funds" subtitle="Explore schemes, NAV history, and fund analytics.">
      <input
        className="search"
        placeholder="Search mutual funds…"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
      />
      <section className="panel">
        <LoadingOrError query={funds} />
        <Table rows={(funds.data || []).slice(0, 100)} linkKey="scheme_code" linkBase="/mutualfunds/" />
      </section>
    </Page>
  );
}

function SyncControls({
  schemeId,
  type,
  disabled = false,
}: {
  schemeId: string;
  type: 'nav' | 'metrics' | 'enrichment';
  disabled?: boolean;
}) {
  const [busy, setBusy] = React.useState(false);
  const [message, setMessage] = React.useState('');
  const run = async (force: boolean) => {
    setBusy(true);
    setMessage('Queued…');
    try {
      const response = await fetch(
        `/api/v1/market-data/mutual-funds/${encodeURIComponent(schemeId)}/sync/${type}?force=${force}`,
        { method: 'POST' },
      );
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.detail || 'Sync failed');
      setMessage(payload.status || 'Queued');
    } catch (error: any) {
      setMessage(error.message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="panel-sync">
      <button disabled={busy || disabled} onClick={() => run(false)}>
        {busy ? 'Working…' : 'Sync'}
      </button>
      <button disabled={busy || disabled} className="secondary" onClick={() => run(true)}>
        Force sync
      </button>
      {disabled && <small>Sync NAV history first.</small>}
      {message && <small>{message}</small>}
    </div>
  );
}

function Section({
  title,
  children,
  controls,
}: {
  title: string;
  children: React.ReactNode;
  controls?: React.ReactNode;
}) {
  return (
    <details className="panel detail-panel">
      <summary className="panel-heading">
        <h2>{title}</h2>
        {controls}
      </summary>
      {children}
    </details>
  );
}

function FundDetail() {
  const { schemeId = '' } = useParams();
  const detail = useQuery({ queryKey: ['fund', schemeId], queryFn: () => api.fund(schemeId) });
  const history = useQuery({ queryKey: ['fund-history', schemeId], queryFn: () => api.fundHistory(schemeId) });
  const metrics = useQuery({ queryKey: ['fund-metrics', schemeId], queryFn: () => api.fundMetrics(schemeId) });
  const enrichment = useQuery({
    queryKey: ['fund-enrichment', schemeId],
    queryFn: () => api.fundEnrichment(schemeId),
  });
  const similar = useQuery({ queryKey: ['fund-similar', schemeId], queryFn: () => api.fundSimilar(schemeId) });
  const fund = detail.data || {};
  const hasNav = Boolean(history.data?.length);
  const metricRows = Array.isArray(metrics.data) ? metrics.data : metrics.data ? [metrics.data] : [];
  return (
    <Page title={fund.scheme_name || schemeId} subtitle="Mutual-fund detail and analytics.">
      <Link className="back" to="/mutualfunds">
        ← Back to mutual funds
      </Link>
      <section className="detail-grid">
        {Object.entries(fund).map(([key, value]) => (
          <div className="detail-item" key={key}>
            <small>{key.replaceAll('_', ' ')}</small>
            <strong>{String(value ?? '—')}</strong>
          </div>
        ))}
      </section>
      <Section title="NAV history" controls={<SyncControls schemeId={schemeId} type="nav" />}>
        <MarketChart kind="fund" id={schemeId} />
        <details className="daily-data">
          <summary>View daily NAV data</summary>
          <Table rows={history.data || []} />
        </details>
      </Section>
      <Section
        title="Performance and risk"
        controls={<SyncControls schemeId={schemeId} type="metrics" disabled={!hasNav} />}
      >
        {metrics.error ? <div className="empty">{metrics.error.message}</div> : <Table rows={metricRows} />}
      </Section>
      <Section title="Fund facts" controls={<SyncControls schemeId={schemeId} type="enrichment" />}>
        <LoadingOrError query={enrichment} />
        <Table rows={enrichment.data || []} />
      </Section>
      <Section title="Similar funds">
        <Table rows={similar.data || []} linkKey="scheme_code" linkBase="/mutualfunds/" />
      </Section>
    </Page>
  );
}

export default function App() {
  return <Shell />;
}
