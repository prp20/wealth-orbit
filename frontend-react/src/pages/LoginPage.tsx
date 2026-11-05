import React from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api';

export default function LoginPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [params] = useSearchParams();
  const status = useQuery({ queryKey: ['auth-status'], queryFn: api.authStatus });
  const [mode, setMode] = React.useState<'signin' | 'signup' | null>(null);
  const [fullName, setFullName] = React.useState('');
  const [password, setPassword] = React.useState('');
  const [error, setError] = React.useState('');
  const [busy, setBusy] = React.useState(false);
  const signingUp = mode === 'signup' || (mode === null && status.data ? !status.data.password_set : false);
  const next = params.get('next') || '/';

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError('');
    if (!fullName.trim()) {
      setError('Enter your name.');
      return;
    }
    if (password.length < 8) {
      setError('Use at least 8 characters.');
      return;
    }
    setBusy(true);
    try {
      if (signingUp) await api.authSignup(fullName.trim(), password);
      else await api.authLogin(fullName.trim(), password);
      await queryClient.invalidateQueries({ queryKey: ['auth-me'] });
      const destination = next.startsWith('/') && !next.startsWith('//') ? next : '/';
      if (destination === '/') {
        window.location.replace('/ui/');
        return;
      }
      navigate(destination, { replace: true });
    } catch (err: any) {
      setError(err.message || 'That name or password is not right.');
    } finally {
      setBusy(false);
    }
  };

  if (status.isLoading && mode === null) {
    return (
      <section className="panel login-panel">
        <div className="home-note">Loading account…</div>
      </section>
    );
  }

  return (
    <section className="panel login-panel">
      <p className="eyebrow">Local account</p>
      <h1>{signingUp ? 'Create an account' : 'Sign in'}</h1>
      <p className="subtitle">
        {signingUp
          ? 'This creates a portfolio stored only on this computer.'
          : 'Use the name and password for a portfolio on this computer.'}
      </p>
      <form onSubmit={submit}>
        <label className="stock-field">
          <span>Name</span>
          <input
            type="text"
            autoComplete="name"
            value={fullName}
            onChange={(event) => setFullName(event.target.value)}
          />
        </label>
        <label className="stock-field">
          <span>Password</span>
          <input
            type="password"
            autoComplete={signingUp ? 'new-password' : 'current-password'}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </label>
        {error && <p className="login-error">{error}</p>}
        <button className="primary-btn" type="submit" disabled={busy || status.isLoading}>
          {busy ? 'Working…' : signingUp ? 'Create account' : 'Sign in'}
        </button>
      </form>
      <p className="login-switch">
        {signingUp ? (
          <button type="button" onClick={() => { setMode('signin'); setError(''); }}>
            Already have an account? Sign in
          </button>
        ) : (
          <button type="button" onClick={() => { setMode('signup'); setError(''); }}>
            New here? Create an account
          </button>
        )}
      </p>
    </section>
  );
}
