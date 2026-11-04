import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../../api';
import { formatInr, formatPct, formatRatio } from '../../../lib/format';

export default function SimilarFundsPanel({ schemeId }: { schemeId: string }) {
  const similar = useQuery({
    queryKey: ['fund-similar', schemeId],
    queryFn: () => api.fundSimilar(schemeId),
  });
  const rows = similar.data || [];

  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>Similar funds</h2>
          <p className="panel-subtitle">Peers in the same subcategory with latest metrics.</p>
        </div>
      </div>
      {similar.isLoading && <div className="loading">Loading similar funds…</div>}
      {similar.error && <div className="empty">{(similar.error as Error).message}</div>}
      {!similar.isLoading && !rows.length && <div className="empty">No similar funds found.</div>}
      {rows.length > 0 && (
        <div className="table-wrap">
          <table className="stock-table">
            <thead>
              <tr>
                <th>Code</th>
                <th>Name</th>
                <th>AMC</th>
                <th>NAV</th>
                <th>CAGR</th>
                <th>Trailing</th>
                <th>Sharpe</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row: any) => (
                <tr key={row.scheme_code}>
                  <td className="symbol-cell">
                    <Link to={`/mutualfunds/${encodeURIComponent(row.scheme_code)}`}>{row.scheme_code}</Link>
                  </td>
                  <td className="company-cell">{row.scheme_name || '—'}</td>
                  <td>{row.amc_name || '—'}</td>
                  <td>{formatInr(row.latest_nav)}</td>
                  <td>{formatPct(row.cagr)}</td>
                  <td>{formatPct(row.trailing_return)}</td>
                  <td>{formatRatio(row.sharpe)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
