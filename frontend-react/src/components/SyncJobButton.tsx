import React from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { api, SyncJob } from '../api';

const TERMINAL = new Set(['SUCCEEDED', 'FAILED', 'CANCELLED']);

async function pollJob(jobId: string, onUpdate: (job: SyncJob) => void): Promise<SyncJob> {
  for (let attempt = 0; attempt < 120; attempt += 1) {
    const job = await api.syncJob(jobId);
    onUpdate(job);
    if (TERMINAL.has(String(job.status || '').toUpperCase())) return job;
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  throw new Error('Sync is still running; refresh to check status.');
}

export default function SyncJobButton({
  symbol,
  kind,
  invalidateKeys = [],
  label = 'Sync',
}: {
  symbol: string;
  kind: string;
  invalidateKeys?: unknown[][];
  label?: string;
}) {
  const queryClient = useQueryClient();
  const [busy, setBusy] = React.useState(false);
  const [message, setMessage] = React.useState('');
  const [status, setStatus] = React.useState('idle');

  React.useEffect(() => {
    let cancelled = false;
    api.syncStockStatus(symbol, kind)
      .then((payload) => {
        if (cancelled) return;
        setStatus(payload.status || 'idle');
        if (payload.job?.last_error) setMessage(payload.job.last_error);
        else if (payload.job?.status) setMessage(payload.job.status);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [symbol, kind]);

  const run = async (force: boolean) => {
    setBusy(true);
    setMessage('Queued…');
    setStatus('queued');
    try {
      const job = await api.syncStock(symbol, kind, force);
      setStatus(String(job.status || 'QUEUED').toLowerCase());
      setMessage(job.duplicate ? 'Already queued' : job.status || 'Queued');
      const terminal = await pollJob(job.job_id, (current) => {
        setStatus(String(current.status || '').toLowerCase());
        setMessage(current.last_error || current.status || '');
      });
      setStatus(String(terminal.status || '').toLowerCase());
      setMessage(terminal.last_error || terminal.status || 'Done');
      await Promise.all(invalidateKeys.map((key) => queryClient.invalidateQueries({ queryKey: key })));
      await queryClient.invalidateQueries({ queryKey: ['stock', symbol] });
    } catch (error: any) {
      setStatus('failed');
      setMessage(error.message || 'Sync failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="panel-sync">
      <button disabled={busy} onClick={() => run(false)}>
        {busy ? 'Working…' : label}
      </button>
      <button disabled={busy} className="secondary" onClick={() => run(true)}>
        Force sync
      </button>
      <span className={`sync-chip status-${status}`}>{status}</span>
      {message && <small>{message}</small>}
    </div>
  );
}
