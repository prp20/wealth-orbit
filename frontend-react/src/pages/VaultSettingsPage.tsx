import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api';

export default function VaultSettingsPage() {
  const queryClient = useQueryClient();
  const [confirm, setConfirm] = useState('');
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const vault = useQuery({
    queryKey: ['vault'],
    queryFn: api.vaultGet,
    retry: false,
  });

  const summary = useQuery({
    queryKey: ['vault-summary'],
    queryFn: api.vaultPullSummary,
    retry: false,
    enabled: vault.isSuccess,
  });

  const push = useMutation({
    mutationFn: api.vaultPushFromSqlite,
    onSuccess: (data) => {
      setError(null);
      setMessage(
        `Pushed vault version ${data.vault.version} (${data.holdings_count} holdings, ${data.transactions_count} transactions).`,
      );
      queryClient.invalidateQueries({ queryKey: ['vault'] });
      queryClient.invalidateQueries({ queryKey: ['vault-summary'] });
    },
    onError: (err: Error) => {
      setMessage(null);
      setError(err.message);
    },
  });

  const reset = useMutation({
    mutationFn: () => api.vaultReset(confirm),
    onSuccess: (data) => {
      setError(null);
      setMessage(data.message);
      setConfirm('');
      queryClient.invalidateQueries({ queryKey: ['vault'] });
      queryClient.invalidateQueries({ queryKey: ['vault-summary'] });
    },
    onError: (err: Error) => {
      setMessage(null);
      setError(err.message);
    },
  });

  return (
    <>
      <header>
        <p className="eyebrow">Wealth Orbit</p>
        <h1>Encrypted portfolio vault</h1>
        <p className="subtitle">
          Push your local SQLite ledger into Supabase as ciphertext (session pooler). Reset is PC-only and
          irreversible without a new encryption secret.
        </p>
      </header>

      <section className="panel">
        <h2>Status</h2>
        {vault.isLoading && <div className="loading">Loading vault…</div>}
        {vault.error && <div className="empty">{(vault.error as Error).message}</div>}
        {vault.data && (
          <p>
            Generation {vault.data.vault_generation} · version {vault.data.version}
            {vault.data.updated_at ? ` · updated ${vault.data.updated_at}` : ''}
          </p>
        )}
        {summary.data && (
          <p>
            Decrypted summary: {summary.data.holdings_count} holdings, {summary.data.transactions_count}{' '}
            transactions (schema {summary.data.schema_version}).
          </p>
        )}
        {summary.error && vault.isSuccess && (
          <div className="empty">{(summary.error as Error).message}</div>
        )}
      </section>

      <section className="panel">
        <h2>Push from SQLite</h2>
        <p className="subtitle">
          Requires <code>DATABASE_URL</code>, <code>PORTFOLIO_ENCRYPTION_SECRET</code>, and{' '}
          <code>VAULT_USER_ID</code> in <code>.env</code>.
        </p>
        <button type="button" onClick={() => push.mutate()} disabled={push.isPending}>
          {push.isPending ? 'Pushing…' : 'Push local portfolio to vault'}
        </button>
      </section>

      <section className="panel">
        <h2>Reset vault (PC only)</h2>
        <p className="subtitle">
          Deletes the remote ciphertext. Type <strong>RESET</strong>, then rotate{' '}
          <code>PORTFOLIO_ENCRYPTION_SECRET</code> in <code>.env</code> and push again. Update Android with
          the new secret.
        </p>
        <input
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          placeholder="Type RESET"
          aria-label="Confirm reset"
        />{' '}
        <button
          type="button"
          onClick={() => reset.mutate()}
          disabled={reset.isPending || confirm !== 'RESET'}
        >
          {reset.isPending ? 'Resetting…' : 'Reset vault'}
        </button>
      </section>

      {message && <div className="panel">{message}</div>}
      {error && <div className="empty">{error}</div>}
    </>
  );
}
