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
  const [error, setError] = React.useState('');
  const [status, setStatus] = React.useState('idle');
  const [menuOpen, setMenuOpen] = React.useState(false);
  const rootRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    let cancelled = false;
    api.syncStockStatus(symbol, kind)
      .then((payload) => {
        if (cancelled) return;
        setStatus(payload.status || 'idle');
        if (payload.job?.last_error && String(payload.job.status).toUpperCase() === 'FAILED') {
          setError(payload.job.last_error);
        }
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [symbol, kind]);

  React.useEffect(() => {
    if (!menuOpen) return;
    const onDoc = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setMenuOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [menuOpen]);

  const run = async (force: boolean) => {
    setBusy(true);
    setError('');
    setMenuOpen(false);
    setStatus('queued');
    try {
      const job = await api.syncStock(symbol, kind, force);
      setStatus(String(job.status || 'QUEUED').toLowerCase());
      const terminal = await pollJob(job.job_id, (current) => {
        setStatus(String(current.status || '').toLowerCase());
        if (current.last_error && String(current.status).toUpperCase() === 'FAILED') {
          setError(current.last_error);
        }
      });
      const terminalStatus = String(terminal.status || '').toLowerCase();
      setStatus(terminalStatus);
      if (terminalStatus === 'failed') {
        setError(terminal.last_error || 'Sync failed');
      } else {
        setError('');
      }
      await Promise.all(invalidateKeys.map((key) => queryClient.invalidateQueries({ queryKey: key })));
      await queryClient.invalidateQueries({ queryKey: ['stock', symbol] });
    } catch (err: any) {
      setStatus('failed');
      setError(err.message || 'Sync failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="panel-sync" ref={rootRef}>
      <button type="button" disabled={busy} onClick={() => run(false)}>
        {busy ? 'Working…' : label}
      </button>
      <div className="sync-overflow">
        <button
          type="button"
          className="sync-overflow-trigger"
          disabled={busy}
          aria-label="More sync options"
          aria-expanded={menuOpen}
          onClick={() => setMenuOpen((open) => !open)}
        >
          ⋯
        </button>
        {menuOpen && (
          <div className="sync-overflow-menu">
            <button type="button" disabled={busy} onClick={() => run(true)}>
              Force sync
            </button>
          </div>
        )}
      </div>
      <span className={`sync-chip status-${status}`}>{status}</span>
      {error && <small className="sync-error">{error}</small>}
    </div>
  );
}
