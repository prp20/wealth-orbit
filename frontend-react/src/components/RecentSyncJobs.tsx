import { useQuery } from '@tanstack/react-query';
import { api, syncJobFailureMessage } from '../api';
import { formatDisplayDate } from '../lib/format';

function jobLabel(job: {
  entity_type?: string;
  entity_key?: string;
  sync_type?: string;
}) {
  const entity = [job.entity_type, job.entity_key].filter(Boolean).join(' ');
  const kind = job.sync_type || 'sync';
  return entity ? `${entity} · ${kind}` : kind;
}

export default function RecentSyncJobs() {
  const queue = useQuery({
    queryKey: ['sync-queue', 'recent'],
    queryFn: () => api.syncQueue(true, 8),
    refetchInterval: 15_000,
  });
  const jobs = queue.data?.jobs || [];

  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>Recent sync jobs</h2>
          <p className="panel-subtitle">Latest market sync attempts, including failures.</p>
        </div>
      </div>
      {queue.isLoading && <div className="home-note">Loading sync jobs…</div>}
      {queue.error && <div className="home-note">Sync job history could not be loaded.</div>}
      {!queue.isLoading && !queue.error && !jobs.length && (
        <div className="home-note">No sync jobs yet. Update a stock, fund, or indexes to create one.</div>
      )}
      {jobs.length > 0 && (
        <ul className="sync-job-list">
          {jobs.map((job) => {
            const status = String(job.status || 'unknown').toLowerCase();
            const failure = syncJobFailureMessage(job);
            const when = formatDisplayDate(job.completed_at || job.started_at || job.queued_at);
            return (
              <li key={job.job_id} className="sync-job-row">
                <div>
                  <strong>{jobLabel(job)}</strong>
                  <span className={`sync-chip status-${status}`}>{status}</span>
                </div>
                <small>
                  {when}
                  {failure ? ` · ${failure}` : ''}
                </small>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
