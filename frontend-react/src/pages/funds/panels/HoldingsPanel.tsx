import { useQuery } from '@tanstack/react-query';
import { api } from '../../../api';
import SyncJobButton from '../../../components/SyncJobButton';
import { formatDate, formatPct, formatRatio } from '../../../lib/format';

export default function HoldingsPanel({ schemeId }: { schemeId: string }) {
  const holdings = useQuery({
    queryKey: ['fund-holdings', schemeId],
    queryFn: () => api.fundHoldings(schemeId, 20),
  });
  const data = holdings.data;

  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>Portfolio</h2>
          <p className="panel-subtitle">
            Latest monthly disclosure with top holdings, sector/market-cap mix, concentration, and changes vs
            prior month. Sync loads seed/provider disclosures.
          </p>
        </div>
        <SyncJobButton
          entity="fund"
          id={schemeId}
          kind="holdings"
          invalidateKeys={[['fund-holdings', schemeId]]}
        />
      </div>
      {holdings.isLoading && <div className="loading">Loading holdings…</div>}
      {holdings.error && <div className="empty">{(holdings.error as Error).message}</div>}
      {data && data.available === false && <div className="empty">{data.reason || 'No disclosure yet.'}</div>}
      {data?.available && (
        <>
          <p className="result-count">
            As of {formatDate(data.as_of_date)} · source {data.source_name || '—'}
            {data.prior_as_of_date ? ` · prior ${formatDate(data.prior_as_of_date)}` : ''}
            {data.stale ? ' · stale disclosure (>120 days)' : ''}
          </p>
          <section className="metrics compact-metrics snapshot-metrics fund-risk-metrics">
            <div className="metric">
              <small>Equity</small>
              <strong>{formatPct(data.asset_allocation?.equity_pct)}</strong>
            </div>
            <div className="metric">
              <small>Debt</small>
              <strong>{formatPct(data.asset_allocation?.debt_pct)}</strong>
            </div>
            <div className="metric">
              <small>Cash</small>
              <strong>{formatPct(data.asset_allocation?.cash_pct)}</strong>
            </div>
            <div className="metric">
              <small>Top 5</small>
              <strong>{formatPct(data.concentration?.top5_weight)}</strong>
            </div>
            <div className="metric">
              <small>Top 10</small>
              <strong>{formatPct(data.concentration?.top10_weight)}</strong>
            </div>
            <div className="metric">
              <small>HHI</small>
              <strong>{formatRatio(data.concentration?.hhi, 4)}</strong>
            </div>
          </section>

          <h3 style={{ marginTop: 18, fontSize: 14 }}>Top holdings</h3>
          <div className="table-wrap">
            <table className="stock-table">
              <thead>
                <tr>
                  <th>Security</th>
                  <th>ISIN</th>
                  <th>Sector</th>
                  <th>Mcap</th>
                  <th>Weight</th>
                </tr>
              </thead>
              <tbody>
                {(data.top_holdings || []).map((row: any) => (
                  <tr key={`${row.isin || row.security_name}`}>
                    <td className="company-cell">{row.security_name}</td>
                    <td className="symbol-cell">{row.isin || '—'}</td>
                    <td>{row.sector || '—'}</td>
                    <td>{row.market_cap_bucket || '—'}</td>
                    <td>{formatPct(row.weight_pct)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <h3 style={{ marginTop: 18, fontSize: 14 }}>Sector allocation</h3>
          <div className="table-wrap">
            <table className="stock-table">
              <thead>
                <tr>
                  <th>Sector</th>
                  <th>Weight</th>
                </tr>
              </thead>
              <tbody>
                {(data.sector_allocation || []).map((row: any) => (
                  <tr key={row.sector}>
                    <td>{row.sector}</td>
                    <td>{formatPct(row.weight_pct)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <h3 style={{ marginTop: 18, fontSize: 14 }}>Changes vs prior disclosure</h3>
          <p className="panel-subtitle">
            New {(data.changes?.new || []).length} · Exited {(data.changes?.exited || []).length} · Increased{' '}
            {(data.changes?.increased || []).length} · Reduced {(data.changes?.reduced || []).length}
          </p>
        </>
      )}
    </section>
  );
}
