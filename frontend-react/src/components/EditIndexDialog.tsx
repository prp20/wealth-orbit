import React from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { api } from '../api';
import {
  DEFAULT_HISTORY_PERIOD,
  HISTORY_PERIOD_OPTIONS,
  HistoryPeriod,
} from '../lib/addInstrument';
import { indexLabel } from '../lib/homeIndexes';

type Props = {
  open: boolean;
  row: { index_code?: string; index_name?: string; yf_symbol?: string | null } | null;
  onClose: () => void;
};

export default function EditIndexDialog({ open, row, onClose }: Props) {
  const queryClient = useQueryClient();
  const [yfSymbol, setYfSymbol] = React.useState('');
  const [historyPeriod, setHistoryPeriod] = React.useState<HistoryPeriod>(DEFAULT_HISTORY_PERIOD);
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);

  React.useEffect(() => {
    if (!open || !row) return;
    setYfSymbol(String(row.yf_symbol || ''));
    setHistoryPeriod(DEFAULT_HISTORY_PERIOD);
    setError(null);
    setBusy(false);
  }, [open, row?.index_code, row?.yf_symbol]);

  if (!open || !row) return null;

  const code = String(row.index_code || '').toUpperCase();

  const save = async () => {
    const trimmed = yfSymbol.trim();
    if (!trimmed) {
      setError('Enter a Yahoo Finance symbol');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.updateIndexInstrument(code, trimmed, true, historyPeriod);
      await queryClient.invalidateQueries({ queryKey: ['benchmarks'] });
      await queryClient.invalidateQueries({ queryKey: ['benchmark-summary'] });
      onClose();
    } catch (err) {
      setError((err as Error).message || 'Could not update index');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="dialog-backdrop" role="presentation" onClick={onClose}>
      <div
        className="dialog-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="edit-index-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="dialog-header">
          <h2 id="edit-index-title">Edit index</h2>
          <button type="button" className="dialog-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>
        <p className="dialog-copy">
          Update the Yahoo Finance symbol for {indexLabel(row)} ({code}) and resync history.
        </p>
        <label className="stock-field">
          <span>Yahoo symbol</span>
          <input
            className="search"
            value={yfSymbol}
            onChange={(event) => setYfSymbol(event.target.value)}
            placeholder="^CRSLDX or NIFTYMIDCAP150.NS"
            autoFocus
          />
        </label>
        <label className="stock-field" style={{ marginTop: 12 }}>
          <span>History depth</span>
          <select
            value={historyPeriod}
            onChange={(event) => setHistoryPeriod(event.target.value as HistoryPeriod)}
          >
            {HISTORY_PERIOD_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        {error && <div className="dialog-error">{error}</div>}
        <div className="dialog-actions">
          <button type="button" className="secondary" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button type="button" onClick={save} disabled={busy}>
            {busy ? 'Saving…' : 'Save & sync'}
          </button>
        </div>
      </div>
    </div>
  );
}
