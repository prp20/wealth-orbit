import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import {
  api,
  InstrumentPreview,
  TrackInstrumentResult,
} from '../api';
import {
  InstrumentKind,
  addInstrumentCodeLabel,
  fundDetailPath,
  stockDetailPath,
  validateAddInstrumentCode,
} from '../lib/addInstrument';

export type { InstrumentKind };

type Props = {
  open: boolean;
  onClose: () => void;
  initialKind?: InstrumentKind;
  initialCode?: string;
  allowedKinds?: InstrumentKind[];
  onTracked?: (result: TrackInstrumentResult, kind: InstrumentKind) => void;
};

const KIND_LABEL: Record<InstrumentKind, string> = {
  stock: 'Stock',
  fund: 'Fund',
  index: 'Index',
};

function previewLabel(preview: InstrumentPreview | null): string {
  if (!preview) return '';
  if (preview.instrument_type === 'stock') {
    return `${preview.trading_symbol} — ${preview.company_name || ''}`.trim();
  }
  if (preview.instrument_type === 'mutual_fund') {
    return `${preview.scheme_code} — ${preview.scheme_name || ''}`.trim();
  }
  return `${preview.index_code} — ${preview.index_name || preview.yf_symbol || ''}`.trim();
}

export default function AddInstrumentDialog({
  open,
  onClose,
  initialKind = 'stock',
  initialCode = '',
  allowedKinds = ['stock', 'fund', 'index'],
  onTracked,
}: Props) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const kinds = allowedKinds.length ? allowedKinds : (['stock'] as InstrumentKind[]);
  const [kind, setKind] = React.useState<InstrumentKind>(
    kinds.includes(initialKind) ? initialKind : kinds[0],
  );
  const [code, setCode] = React.useState(initialCode);
  const [yfSymbol, setYfSymbol] = React.useState('');
  const [preview, setPreview] = React.useState<InstrumentPreview | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [info, setInfo] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState<'preview' | 'add' | null>(null);

  React.useEffect(() => {
    if (!open) return;
    setKind(kinds.includes(initialKind) ? initialKind : kinds[0]);
    setCode(initialCode);
    setYfSymbol('');
    setPreview(null);
    setError(null);
    setInfo(null);
    setBusy(null);
  }, [open, initialKind, initialCode, kinds.join('|')]);

  if (!open) return null;

  const runPreview = async () => {
    const trimmed = code.trim();
    const validation = validateAddInstrumentCode(code, 'preview');
    if (validation) {
      setError(validation);
      return;
    }
    setBusy('preview');
    setError(null);
    setInfo(null);
    setPreview(null);
    try {
      if (kind === 'stock') setPreview(await api.previewStockInstrument(trimmed));
      else if (kind === 'fund') setPreview(await api.previewFundInstrument(trimmed));
      else setPreview(await api.previewIndexInstrument(trimmed, yfSymbol.trim()));
    } catch (err) {
      setError((err as Error).message || 'Could not resolve this code');
    } finally {
      setBusy(null);
    }
  };

  const runAdd = async () => {
    const trimmed = code.trim();
    const validation = validateAddInstrumentCode(code, 'add');
    if (validation) {
      setError(validation);
      return;
    }
    setBusy('add');
    setError(null);
    setInfo(null);
    try {
      let result: TrackInstrumentResult;
      if (kind === 'stock') result = await api.trackStockInstrument(trimmed, true);
      else if (kind === 'fund') result = await api.trackFundInstrument(trimmed, true);
      else result = await api.trackIndexInstrument(trimmed, yfSymbol.trim(), true);

      if (result.already_tracked) {
        setInfo('Already tracked — opening existing master and syncing history.');
      }
      onTracked?.(result, kind);
      await queryClient.invalidateQueries({ queryKey: ['stocks'] });
      await queryClient.invalidateQueries({ queryKey: ['funds'] });
      await queryClient.invalidateQueries({ queryKey: ['benchmark-summary'] });

      if (kind === 'stock') {
        const symbol = String(result.master.trading_symbol || trimmed);
        onClose();
        navigate(stockDetailPath(symbol));
        return;
      }
      if (kind === 'fund') {
        const scheme = String(result.master.scheme_code || trimmed);
        onClose();
        navigate(fundDetailPath(scheme));
        return;
      }
      onClose();
    } catch (err) {
      setError((err as Error).message || 'Could not add this instrument');
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="dialog-backdrop" role="presentation" onClick={onClose}>
      <div
        className="dialog-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="add-instrument-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="dialog-header">
          <h2 id="add-instrument-title">Add instrument</h2>
          <button type="button" className="dialog-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>
        <p className="dialog-copy">
          India-first: NSE trading symbol, AMFI scheme code, or index code (+ Yahoo when needed).
        </p>

        {kinds.length > 1 && (
          <div className="dialog-tabs" role="tablist">
            {kinds.map((item) => (
              <button
                key={item}
                type="button"
                role="tab"
                aria-selected={kind === item}
                className={kind === item ? 'active' : undefined}
                onClick={() => {
                  setKind(item);
                  setPreview(null);
                  setError(null);
                  setInfo(null);
                }}
              >
                {KIND_LABEL[item]}
              </button>
            ))}
          </div>
        )}

        <label className="stock-field">
          <span>{addInstrumentCodeLabel(kind)}</span>
          <input
            className="search"
            value={code}
            onChange={(event) => {
              setCode(event.target.value);
              setPreview(null);
              setError(null);
              setInfo(null);
            }}
            placeholder={kind === 'stock' ? 'RELIANCE' : kind === 'fund' ? '120503' : 'NIFTY50'}
            autoFocus
          />
        </label>

        {kind === 'index' && (
          <label className="stock-field">
            <span>Yahoo symbol (required if not in the India allowlist)</span>
            <input
              className="search"
              value={yfSymbol}
              onChange={(event) => {
                setYfSymbol(event.target.value);
                setPreview(null);
              }}
              placeholder="^NSEI"
            />
          </label>
        )}

        {preview && <div className="dialog-preview">Preview: {previewLabel(preview)}</div>}
        {info && <div className="dialog-info">{info}</div>}
        {error && <div className="dialog-error">{error}</div>}

        <div className="dialog-actions">
          <button type="button" className="secondary" disabled={busy !== null} onClick={runPreview}>
            {busy === 'preview' ? 'Previewing…' : 'Preview'}
          </button>
          <button type="button" disabled={busy !== null} onClick={runAdd}>
            {busy === 'add' ? 'Adding…' : 'Add & sync history'}
          </button>
        </div>
      </div>
    </div>
  );
}
