import { useQuery } from '@tanstack/react-query';
import { api } from '../../../api';
import SyncJobButton from '../../../components/SyncJobButton';
import { formatDate } from '../../../lib/format';

export default function BenchmarkPanel({ schemeId, fund }: { schemeId: string; fund: any }) {
  const benchmark = useQuery({
    queryKey: ['fund-benchmark', schemeId],
    queryFn: () => api.fundBenchmark(schemeId),
  });
  const mapped = fund?.benchmark?.available
    ? fund.benchmark
    : benchmark.data?.index_code
      ? { available: true, ...benchmark.data }
      : benchmark.data;
  const available = Boolean(mapped?.available && mapped?.index_code);

  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>Benchmark</h2>
          <p className="panel-subtitle">Mapped index used for overlay and relative metrics.</p>
        </div>
        <SyncJobButton
          entity="fund"
          id={schemeId}
          kind="benchmark"
          label="Update benchmark"
          invalidateKeys={[
            ['fund-benchmark', schemeId],
            ['fund-benchmark-history', schemeId],
            ['fund', schemeId],
          ]}
        />
      </div>
      {benchmark.isLoading && !mapped && <div className="loading">Loading benchmark…</div>}
      {benchmark.error && !mapped && <div className="empty">{(benchmark.error as Error).message}</div>}
      {!available && (
        <div className="empty">
          {mapped?.reason || 'No benchmark is mapped for this scheme.'}
        </div>
      )}
      {available && (
        <div className="detail-grid fund-facts-grid">
          <div className="detail-item">
            <small>Index code</small>
            <strong>{mapped.index_code}</strong>
          </div>
          <div className="detail-item">
            <small>Index name</small>
            <strong>{mapped.index_name || '—'}</strong>
          </div>
          <div className="detail-item">
            <small>History through</small>
            <strong>{formatDate(fund?.freshness?.latest_benchmark_history_date)}</strong>
          </div>
        </div>
      )}
    </section>
  );
}
