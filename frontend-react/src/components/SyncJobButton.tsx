import React from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { api, SyncJob, syncJobFailureMessage } from '../api';

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

function quietStatus(status: string, hideSucceeded: boolean) {
  return hideSucceeded && status === 'succeeded' ? 'idle' : status;
}

export default function SyncJobButton({
  entity = 'stock',
  id,
  symbol,
  kind,
  invalidateKeys = [],
  label = 'Sync',
  startJob,
  loadStatus,
  hideSucceeded = false,
  thenKind,
}: {
  entity?: 'stock' | 'fund';
  id?: string;
  /** @deprecated Prefer `id`; kept for stock call sites. */
  symbol?: string;
  kind: string;
  invalidateKeys?: unknown[][];
  label?: string;
  startJob?: () => Promise<SyncJob>;
  loadStatus?: () => Promise<{ status: string; job: SyncJob | null }>;
  hideSucceeded?: boolean;
  /** After this fund job succeeds, enqueue and poll a second kind. */
  thenKind?: string;
}) {
  const queryClient = useQueryClient();
  const entityId = id || symbol || '';
  const custom = Boolean(startJob);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState('');
  const [status, setStatus] = React.useState('idle');
  const [menuOpen, setMenuOpen] = React.useState(false);
  const rootRef = React.useRef<HTMLDivElement>(null);
  const startJobRef = React.useRef(startJob);
  const loadStatusRef = React.useRef(loadStatus);
  startJobRef.current = startJob;
  loadStatusRef.current = loadStatus;

  React.useEffect(() => {
    if (!custom && !entityId) return;
    if (custom && !loadStatusRef.current) return;
    let cancelled = false;
    const statusPromise = custom
      ? loadStatusRef.current!()
      : entity === 'fund'
        ? api.syncFundStatus(entityId, kind)
        : api.syncStockStatus(entityId, kind);
    statusPromise
      .then((payload) => {
        if (cancelled) return;
        const failure = syncJobFailureMessage(payload.job);
        const next = failure ? 'failed' : payload.status || 'idle';
        setStatus(quietStatus(next, hideSucceeded));
        setError(failure || '');
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [custom, entity, entityId, kind, hideSucceeded]);

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
      const job = custom
        ? await startJobRef.current!()
        : entity === 'fund'
          ? await api.syncFundKind(entityId, kind, force)
          : await api.syncStock(entityId, kind, force);
      setStatus(quietStatus(String(job.status || 'QUEUED').toLowerCase(), hideSucceeded));
      let terminal = await pollJob(job.job_id, (current) => {
        const failure = syncJobFailureMessage(current);
        const next = failure ? 'failed' : String(current.status || '').toLowerCase();
        setStatus(quietStatus(next, hideSucceeded));
        if (failure) setError(failure);
      });
      let failure = syncJobFailureMessage(terminal);
      if (!failure && thenKind && !custom && entity === 'fund') {
        const follow = await api.syncFundKind(entityId, thenKind, force);
        setStatus(quietStatus(String(follow.status || 'QUEUED').toLowerCase(), hideSucceeded));
        terminal = await pollJob(follow.job_id, (current) => {
          const followFailure = syncJobFailureMessage(current);
          const next = followFailure ? 'failed' : String(current.status || '').toLowerCase();
          setStatus(quietStatus(next, hideSucceeded));
          if (followFailure) setError(followFailure);
        });
        failure = syncJobFailureMessage(terminal);
      }
      if (failure) {
        setStatus('failed');
        setError(failure);
      } else {
        setStatus(quietStatus(String(terminal.status || '').toLowerCase(), hideSucceeded));
        setError('');
      }
      await Promise.all(invalidateKeys.map((key) => queryClient.invalidateQueries({ queryKey: key })));
      if (!custom) {
        if (entity === 'fund') {
          await queryClient.invalidateQueries({ queryKey: ['fund', entityId] });
        } else {
          await queryClient.invalidateQueries({ queryKey: ['stock', entityId] });
        }
      }
    } catch (err: any) {
      setStatus('failed');
      setError(err.message || 'Sync failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="panel-sync" ref={rootRef}>
      <button type="button" disabled={busy || (!custom && !entityId)} onClick={() => run(false)}>
        {busy ? 'Working…' : label}
      </button>
      {!custom && (
        <div className="sync-overflow">
          <button
            type="button"
            className="sync-overflow-trigger"
            disabled={busy || !entityId}
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
      )}
      {!(hideSucceeded && (status === 'idle' || status === 'succeeded')) && (
        <span className={`sync-chip status-${status}`}>{status}</span>
      )}
      {error && <small className="sync-error">{error}</small>}
    </div>
  );
}
