import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api';
import PageHeader from '../components/PageHeader';
import { formatInr, formatRatio } from '../lib/format';

const SLEEVE_LABELS: Record<string, string> = {
  MUTUAL_FUND: 'Mutual funds',
  STOCK: 'Stocks',
};

function sleeveLabel(assetType: string) {
  return SLEEVE_LABELS[assetType] || assetType.replaceAll('_', ' ').toLowerCase().replace(/\b\w/g, (char) => char.toUpperCase());
}

function fundHref(row: { asset_name?: string; scheme_code?: string | null }) {
  if (row.scheme_code) return `/mutualfunds/${encodeURIComponent(row.scheme_code)}`;
  const name = row.asset_name || '';
  return name ? `/mutualfunds?search=${encodeURIComponent(name)}` : '/mutualfunds';
}

function classLabel(value: string) {
  const text = String(value || '').replaceAll('_', ' ').toLowerCase();
  return text ? text.replace(/\b\w/g, (char) => char.toUpperCase()) : '—';
}

export default function PortfolioPage() {
  const portfolios = useQuery({ queryKey: ['portfolios'], queryFn: api.portfolios });
  const portfolioId = portfolios.data?.[0]?.portfolio_id;
  const holdings = useQuery({
    queryKey: ['holdings', portfolioId],
    queryFn: () => api.holdings(portfolioId),
    enabled: Boolean(portfolioId),
  });
  const rows = [...(holdings.data || [])].sort(
    (a, b) => Number(b.invested_amount || 0) - Number(a.invested_amount || 0),
  );
  const invested = rows.reduce((sum, holding) => sum + Number(holding.invested_amount || 0), 0);
  const sleeves = new Map<string, number>();
  for (const row of rows) {
    const key = String(row.asset_type || 'OTHER');
    sleeves.set(key, (sleeves.get(key) || 0) + Number(row.invested_amount || 0));
  }
  const sleeveRows = Array.from(sleeves.entries()).filter(([, amount]) => amount !== 0);

  return (
    <>
      <PageHeader title="Portfolio" subtitle="Cost of what you hold. Positions are not marked to market." />
      {(portfolios.isLoading || (portfolioId && holdings.isLoading)) && <div className="loading">Loading portfolio…</div>}
      {(portfolios.error || holdings.error) && <div className="empty">Portfolio could not be loaded.</div>}
      {!portfolios.isLoading && !holdings.isLoading && !portfolios.error && !holdings.error && !rows.length && (
        <section className="panel">
          <div className="home-note">No holdings yet. Research can continue without a portfolio.</div>
        </section>
      )}
      {rows.length > 0 && (
        <section className="panel">
          <div className="home-stats portfolio-stats">
            <div>
              <small>Invested</small>
              <strong>{formatInr(invested)}</strong>
            </div>
            <div>
              <small>Holdings</small>
              <strong>{rows.length}</strong>
            </div>
            <div className="home-stat-quiet">
              <small>Market gains</small>
              <strong>Not available</strong>
            </div>
          </div>
          <p className="panel-subtitle home-cost-note">Invested is cost. Positions are not marked to market.</p>
          {sleeveRows.length > 0 && (
            <ul className="sleeve-list">
              {sleeveRows.map(([type, amount]) => {
                const share = invested ? (amount / invested) * 100 : null;
                return (
                  <li key={type}>
                    <div className="sleeve-row">
                      <span>{sleeveLabel(type)}</span>
                      <span className="sleeve-amount">
                        {formatInr(amount)}
                        <em>{share == null ? '—' : `${formatRatio(share, 1)}%`}</em>
                      </span>
                    </div>
                    <div className="sleeve-track" aria-hidden="true">
                      <i className={type === 'STOCK' ? 'sleeve-stock' : 'sleeve-fund'} style={{ width: `${share ?? 0}%` }} />
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
          <div className="table-wrap holdings-wrap">
            <table className="holdings-table">
              <thead>
                <tr>
                  <th>Holding</th>
                  <th>Sleeve</th>
                  <th>Class</th>
                  <th className="num">Quantity</th>
                  <th className="num">Average cost</th>
                  <th className="num">Invested</th>
                  <th className="num">Share</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => {
                  const amount = Number(row.invested_amount || 0);
                  const share = invested ? (amount / invested) * 100 : null;
                  return (
                    <tr key={row.holding_id}>
                      <td className="holding-name">
                        {String(row.asset_type) === 'MUTUAL_FUND' ? (
                          <Link to={fundHref(row)}>{row.asset_name}</Link>
                        ) : (
                          row.asset_name
                        )}
                      </td>
                      <td>{sleeveLabel(String(row.asset_type || ''))}</td>
                      <td>{classLabel(String(row.investment_class || ''))}</td>
                      <td className="num">{formatRatio(row.current_quantity)}</td>
                      <td className="num">{formatInr(row.average_cost_per_unit)}</td>
                      <td className="num">{formatInr(amount)}</td>
                      <td className="num">{share == null ? '—' : `${formatRatio(share, 1)}%`}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </>
  );
}
