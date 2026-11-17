import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api';
import AddInstrumentDialog from '../components/AddInstrumentDialog';
import EditIndexDialog from '../components/EditIndexDialog';
import IndexTable from '../components/IndexTable';
import PageHeader from '../components/PageHeader';
import SyncJobButton from '../components/SyncJobButton';
import { HOME_INDEXES, SECTOR_INDEXES, rememberExtraIndex } from '../lib/homeIndexes';

const PAGE_SIZE = 25;

function rankIndexCode(code: string) {
  const home = HOME_INDEXES.indexOf(code);
  if (home >= 0) return home;
  const sector = SECTOR_INDEXES.indexOf(code);
  if (sector >= 0) return 100 + sector;
  return 1000;
}

function matchesQuery(row: any, query: string) {
  if (!query) return true;
  const haystack = [row.index_code, row.index_name, row.yf_symbol]
    .map((value) => String(value || '').toLowerCase())
    .join(' ');
  return haystack.includes(query.toLowerCase());
}

export default function IndexesPage() {
  const [query, setQuery] = React.useState('');
  const [debouncedQuery, setDebouncedQuery] = React.useState('');
  const [page, setPage] = React.useState(1);
  const [addOpen, setAddOpen] = React.useState(false);
  const [addCode, setAddCode] = React.useState('');
  const [editRow, setEditRow] = React.useState<any | null>(null);

  React.useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedQuery(query.trim()), 300);
    return () => window.clearTimeout(timer);
  }, [query]);

  React.useEffect(() => {
    setPage(1);
  }, [debouncedQuery]);

  const indexes = useQuery({
    queryKey: ['benchmark-summary', 'all'],
    queryFn: () => api.benchmarkSummary(),
    retry: 1,
  });

  const rows = React.useMemo(() => {
    const list = [...(indexes.data || [])].filter((row) => matchesQuery(row, debouncedQuery));
    list.sort((a, b) => {
      const aCode = String(a.index_code || '').toUpperCase();
      const bCode = String(b.index_code || '').toUpperCase();
      const diff = rankIndexCode(aCode) - rankIndexCode(bCode);
      return diff !== 0 ? diff : aCode.localeCompare(bCode);
    });
    return list;
  }, [indexes.data, debouncedQuery]);

  const totalPages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  const safePage = Math.min(page, totalPages);
  const start = (safePage - 1) * PAGE_SIZE;
  const pageRows = rows.slice(start, start + PAGE_SIZE);
  const showingFrom = rows.length ? start + 1 : 0;
  const showingTo = Math.min(start + PAGE_SIZE, rows.length);

  return (
    <>
      <PageHeader
        title="Indexes"
        subtitle="Browse tracked indexes, fix Yahoo mappings, or add indexes beyond the seed list."
      />

      <section className="panel stock-list-panel">
        <div className="indexes-toolbar">
          <label className="stock-field">
            <span>Search</span>
            <input
              className="search"
              placeholder="Index name, code, or Yahoo…"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>
          <div className="toolbar-actions">
            <SyncJobButton
              kind="PRICES"
              label="Update indexes"
              hideSucceeded
              extendHistory
              startJob={() => api.syncBenchmarks()}
              startExtendJob={(period) => api.syncBenchmarks(undefined, period)}
              loadStatus={() => api.syncBenchmarkStatus()}
              invalidateKeys={[['benchmarks'], ['benchmark-summary']]}
            />
            <button
              type="button"
              className="primary-button"
              onClick={() => {
                setAddCode(debouncedQuery);
                setAddOpen(true);
              }}
            >
              Add index
            </button>
          </div>
        </div>

        {indexes.isLoading && <div className="loading">Loading indexes…</div>}
        {indexes.error && <div className="empty">{(indexes.error as Error).message}</div>}
        {!indexes.isLoading && !rows.length && (
          <div className="empty empty-cta">
            <span>{debouncedQuery ? 'No indexes match this search.' : 'No indexes tracked yet.'}</span>
            {debouncedQuery && (
              <button
                type="button"
                className="primary-button"
                onClick={() => {
                  setAddCode(debouncedQuery);
                  setAddOpen(true);
                }}
              >
                Add “{debouncedQuery}” as index?
              </button>
            )}
          </div>
        )}

        <AddInstrumentDialog
          open={addOpen}
          onClose={() => setAddOpen(false)}
          initialKind="index"
          initialCode={addCode}
          allowedKinds={['index']}
          onTracked={(result) => {
            const code = String(result.master.index_code || '').toUpperCase();
            if (code) rememberExtraIndex(code);
          }}
        />
        <EditIndexDialog open={Boolean(editRow)} row={editRow} onClose={() => setEditRow(null)} />

        {rows.length > 0 && (
          <>
            <p className="result-count">
              Showing {showingFrom}–{showingTo} of {rows.length}
            </p>
            <IndexTable rows={pageRows} onEdit={setEditRow} />
            <div className="pager">
              <button type="button" disabled={safePage <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>
                Previous
              </button>
              <span>
                Page {safePage} of {totalPages}
              </span>
              <button
                type="button"
                disabled={safePage >= totalPages}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              >
                Next
              </button>
            </div>
          </>
        )}
      </section>
    </>
  );
}
