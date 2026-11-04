import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../../api';
import SyncJobButton from '../../../components/SyncJobButton';

const STATEMENT_TYPES = [
  { id: 'PL', label: 'Profit & loss' },
  { id: 'BS', label: 'Balance sheet' },
  { id: 'CF', label: 'Cash flow' },
] as const;

export default function StatementsPanel({ symbol }: { symbol: string }) {
  const [period, setPeriod] = React.useState('ANNUAL');
  const [basis, setBasis] = React.useState('CONSOLIDATED');
  const [statementType, setStatementType] = React.useState<(typeof STATEMENT_TYPES)[number]['id']>('PL');

  const rows = useQuery({
    queryKey: ['stock-statements', symbol, period, basis, statementType],
    queryFn: () =>
      api.stockFundamentals(
        symbol,
        new URLSearchParams({
          reporting_period: period,
          reporting_basis: basis,
          statement_type: statementType,
        }).toString(),
      ),
  });

  const data = rows.data || [];
  const periods = Array.from(new Set(data.map((row: any) => String(row.period_end_date)))).slice(0, 6);
  const metrics = Array.from(new Set(data.map((row: any) => row.metric_code as string)));
  const valueMap = new Map<string, unknown>();
  for (const row of data) {
    valueMap.set(`${row.metric_code}|${row.period_end_date}`, row.metric_value);
  }

  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>Financial statements</h2>
          <p className="panel-subtitle">
            Annual/quarterly lines with standalone and consolidated kept distinct. Source: Screener
            (on-demand sync).
          </p>
        </div>
        <SyncJobButton
          symbol={symbol}
          kind="fundamentals"
          invalidateKeys={[
            ['stock-statements', symbol],
            ['stock-fundamentals-summary', symbol],
            ['stock-fundamentals', symbol],
          ]}
        />
      </div>
      <div className="filters">
        <select value={period} onChange={(event) => setPeriod(event.target.value)}>
          <option value="ANNUAL">Annual</option>
          <option value="QUARTERLY">Quarterly</option>
        </select>
        <select value={basis} onChange={(event) => setBasis(event.target.value)}>
          <option value="CONSOLIDATED">Consolidated</option>
          <option value="STANDALONE">Standalone</option>
        </select>
        <div className="fund-tabs" style={{ margin: 0, border: 0 }} aria-label="Statement type">
          {STATEMENT_TYPES.map((item) => (
            <button
              key={item.id}
              type="button"
              className={statementType === item.id ? 'active' : undefined}
              onClick={() => setStatementType(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>
      {rows.isLoading && <div className="loading">Loading statements…</div>}
      {rows.error && <div className="empty">{(rows.error as Error).message}</div>}
      {!rows.isLoading && !periods.length && (
        <div className="empty">No {statementType} rows for {basis.toLowerCase()} {period.toLowerCase()}. Sync fundamentals to pull Screener data.</div>
      )}
      {periods.length > 0 && (
        <div className="table-wrap">
          <table className="stock-table">
            <thead>
              <tr>
                <th>Metric</th>
                {periods.map((item) => (
                  <th key={item}>{String(item).slice(0, 10)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {metrics.map((code) => {
                const name = data.find((row: any) => row.metric_code === code)?.metric_name || code;
                return (
                  <tr key={code}>
                    <td>{name}</td>
                    {periods.map((item) => {
                      const value = valueMap.get(`${code}|${item}`);
                      return <td key={item}>{value == null ? '—' : String(value)}</td>;
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
