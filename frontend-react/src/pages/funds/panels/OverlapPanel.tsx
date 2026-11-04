import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { api } from '../../../api';
import { formatDate, formatPct } from '../../../lib/format';

export default function OverlapPanel({ schemeCodes }: { schemeCodes: string[] }) {
  const codes = schemeCodes.filter(Boolean).slice(0, 10);
  const overlap = useQuery({
    queryKey: ['fund-overlap', codes.join(',')],
    queryFn: () => api.fundOverlap(codes),
    enabled: codes.length >= 2,
  });

  if (codes.length < 2) {
    return (
      <div className="empty">
        Select at least two schemes to compute overlap. Use the{' '}
        <Link to="/mutualfunds/screen">screener</Link> or compare page.
      </div>
    );
  }

  const data = overlap.data;
  const pairs = data?.pairs || [];

  return (
    <section className="panel" style={{ marginTop: 14 }}>
      <div className="panel-heading">
        <div>
          <h2>Holdings overlap</h2>
          <p className="panel-subtitle">
            Method: sum of min weights over securities matched by ISIN (else name). Stale disclosures are flagged.
          </p>
        </div>
      </div>
      {overlap.isLoading && <div className="loading">Computing overlap…</div>}
      {overlap.error && <div className="empty">{(overlap.error as Error).message}</div>}
      {data?.schemes && (
        <p className="result-count">
          {(data.schemes || [])
            .map(
              (s: any) =>
                `${s.scheme_code}${s.available ? ` @ ${formatDate(s.as_of_date)}` : ' (no disclosure)'}${
                  s.stale ? ' stale' : ''
                }`,
            )
            .join(' · ')}
        </p>
      )}
      {pairs.length > 0 && (
        <div className="table-wrap">
          <table className="stock-table">
            <thead>
              <tr>
                <th>Pair</th>
                <th>Overlap</th>
                <th>Common names</th>
                <th>Notes</th>
              </tr>
            </thead>
            <tbody>
              {pairs.map((pair: any) => (
                <tr key={`${pair.scheme_a}-${pair.scheme_b}`}>
                  <td>
                    <Link to={`/mutualfunds/${encodeURIComponent(pair.scheme_a)}`}>{pair.scheme_a}</Link>
                    {' × '}
                    <Link to={`/mutualfunds/${encodeURIComponent(pair.scheme_b)}`}>{pair.scheme_b}</Link>
                  </td>
                  <td>{pair.available ? formatPct(pair.overlap_score) : '—'}</td>
                  <td>{pair.available ? pair.common_count : '—'}</td>
                  <td>
                    {!pair.available
                      ? pair.reason || 'Unavailable'
                      : pair.stale_warning
                        ? 'Stale disclosure on one/both'
                        : 'OK'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {pairs[0]?.available && (pairs[0].common_holdings || []).length > 0 && (
        <>
          <h3 style={{ marginTop: 18, fontSize: 14 }}>
            Common holdings ({pairs[0].scheme_a} × {pairs[0].scheme_b})
          </h3>
          <div className="table-wrap">
            <table className="stock-table">
              <thead>
                <tr>
                  <th>Security</th>
                  <th>Weight A</th>
                  <th>Weight B</th>
                  <th>Min</th>
                </tr>
              </thead>
              <tbody>
                {(pairs[0].common_holdings || []).slice(0, 15).map((row: any) => (
                  <tr key={row.isin || row.security_name}>
                    <td className="company-cell">{row.security_name}</td>
                    <td>{formatPct(row.weight_a)}</td>
                    <td>{formatPct(row.weight_b)}</td>
                    <td>{formatPct(row.min_weight)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}
