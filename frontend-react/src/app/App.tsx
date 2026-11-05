import React from 'react';
import { Link, NavLink, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api';
import LoginPage from '../pages/LoginPage';
import StockListPage from '../pages/stocks/StockListPage';
import StockDetailPage from '../pages/stocks/StockDetailPage';
import FundListPage from '../pages/funds/FundListPage';
import FundDetailPage from '../pages/funds/FundDetailPage';
import FundScreenerPage from '../pages/funds/FundScreenerPage';
import FundComparePage from '../pages/funds/FundComparePage';
import DashboardPage from '../pages/DashboardPage';
import PortfolioPage from '../pages/PortfolioPage';

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

function RequireAuth({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const account = useQuery({ queryKey: ['auth-me'], queryFn: api.authMe, retry: false });
  if (account.isLoading) return <div className="loading">Loading account…</div>;
  if (!account.data?.signed_in) {
    const next = encodeURIComponent(location.pathname);
    return <Navigate replace to={`/login?next=${next}`} />;
  }
  return <>{children}</>;
}

function Shell() {
  const location = useLocation();
  const queryClient = useQueryClient();
  const account = useQuery({ queryKey: ['auth-me'], queryFn: api.authMe, retry: false });
  const signedIn = account.data?.signed_in === true;

  const logout = async () => {
    const onLedger = location.pathname === '/portfolio' || location.pathname === '/transactions';
    await api.authLogout();
    queryClient.removeQueries({ queryKey: ['auth-me'] });
    queryClient.removeQueries({ queryKey: ['portfolios'] });
    queryClient.removeQueries({ queryKey: ['holdings'] });
    queryClient.removeQueries({ queryKey: ['transactions'] });
    if (onLedger) {
      window.location.replace('/ui/');
    }
  };

  return (
    <div className="shell">
      <aside>
        <div className="brand">
          wealth<span>orbit</span>
          <small>Investment workspace</small>
        </div>
        <nav>
          <NavLink to="/" end>Dashboard</NavLink>
          {signedIn && <NavLink to="/portfolio">Portfolio</NavLink>}
          {signedIn && <NavLink to="/transactions">Transactions</NavLink>}
          <NavLink to="/mutualfunds">Mutual funds</NavLink>
          <NavLink to="/stocks">Stocks</NavLink>
        </nav>
        <div className="account-footer">
          {signedIn ? (
            <>
              <strong>{account.data?.full_name || 'Portfolio owner'}</strong>
              <small>Personal portfolio</small>
              <button type="button" onClick={logout}>Log out</button>
            </>
          ) : (
            <NavLink to="/login">Sign in</NavLink>
          )}
        </div>
      </aside>
      <main>
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/portfolio" element={<RequireAuth><PortfolioPage /></RequireAuth>} />
          <Route path="/transactions" element={<RequireAuth><TransactionsPage /></RequireAuth>} />
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
