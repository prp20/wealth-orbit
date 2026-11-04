import React from 'react';
import { Link, NavLink, Navigate, Route, Routes } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api';
import StockListPage from '../pages/stocks/StockListPage';
import StockDetailPage from '../pages/stocks/StockDetailPage';
import FundListPage from '../pages/funds/FundListPage';
import FundDetailPage from '../pages/funds/FundDetailPage';
import FundScreenerPage from '../pages/funds/FundScreenerPage';
import FundComparePage from '../pages/funds/FundComparePage';
import { formatInr } from '../lib/format';

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
          <Route path="/mutualfunds" element={<FundListPage />} />
          <Route path="/mutualfunds/screen" element={<FundScreenerPage />} />
          <Route path="/mutualfunds/compare" element={<FundComparePage />} />
          <Route path="/mutualfunds/:schemeId" element={<FundDetailPage />} />
          <Route path="/mutual-funds" element={<Navigate replace to="/mutualfunds" />} />
          <Route path="/mutual-funds/screen" element={<Navigate replace to="/mutualfunds/screen" />} />
          <Route path="/mutual-funds/compare" element={<Navigate replace to="/mutualfunds/compare" />} />
          <Route path="/mutual-funds/:schemeId" element={<FundDetailPage />} />
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
          <strong>{formatInr(invested)}</strong>
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

export default function App() {
  return <Shell />;
}
