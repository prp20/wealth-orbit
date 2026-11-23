import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { api, GlossaryAgentChatMessage, GlossaryAgentChatResult } from '../api';
import { AssistantMessage, SuggestionRow } from './glossaryChatUi';

const SESSIONS_KEY = 'wealth-orbit.glossary.sessions.v1';

type ChatEntry =
  | { id: string; role: 'user'; text: string }
  | { id: string; role: 'assistant'; result: GlossaryAgentChatResult };

type GlossarySession = {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  entries: ChatEntry[];
};

function newId(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function createSession(partial?: Partial<GlossarySession>): GlossarySession {
  const now = Date.now();
  return {
    id: partial?.id || newId('s'),
    title: partial?.title || 'New chat',
    createdAt: partial?.createdAt || now,
    updatedAt: partial?.updatedAt || now,
    entries: partial?.entries || [],
  };
}

function loadSessions(): GlossarySession[] {
  try {
    const raw = localStorage.getItem(SESSIONS_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((item) => item && typeof item.id === 'string' && Array.isArray(item.entries));
  } catch {
    return [];
  }
}

function saveSessions(sessions: GlossarySession[]) {
  localStorage.setItem(SESSIONS_KEY, JSON.stringify(sessions.slice(0, 40)));
}

function titleFromEntries(entries: ChatEntry[]): string {
  const firstUser = entries.find((entry) => entry.role === 'user');
  if (!firstUser || firstUser.role !== 'user') return 'New chat';
  const text = firstUser.text.trim().replace(/\s+/g, ' ');
  return text.length > 42 ? `${text.slice(0, 42)}…` : text;
}

function buildAgentHistory(entries: ChatEntry[]): GlossaryAgentChatMessage[] {
  const history: GlossaryAgentChatMessage[] = [];
  for (const entry of entries) {
    if (entry.role === 'user') {
      history.push({ role: 'user', content: entry.text });
      continue;
    }
    history.push({ role: 'assistant', content: entry.result.assistant_message });
  }
  return history;
}

export default function GlossaryChatPage() {
  const boot = React.useMemo(() => {
    const stored = loadSessions();
    const list = stored.length ? stored : [createSession()];
    return { list, activeId: list[0].id };
  }, []);
  const [sessions, setSessions] = React.useState<GlossarySession[]>(boot.list);
  const [activeId, setActiveId] = React.useState(boot.activeId);
  const [draft, setDraft] = React.useState('');
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState('');
  const [sessionsOpen, setSessionsOpen] = React.useState(false);
  const logRef = React.useRef<HTMLDivElement>(null);
  const terms = useQuery({ queryKey: ['glossary-terms'], queryFn: api.glossaryTerms, staleTime: 60 * 60 * 1000 });

  const active = sessions.find((session) => session.id === activeId) || sessions[0];
  const entries = active?.entries || [];

  React.useEffect(() => {
    saveSessions(sessions);
  }, [sessions]);

  React.useEffect(() => {
    const node = logRef.current;
    if (!node) return;
    node.scrollTop = node.scrollHeight;
  }, [entries.length, busy, activeId]);

  const updateActive = React.useCallback(
    (mutator: (session: GlossarySession) => GlossarySession) => {
      setSessions((prev) => {
        const list = prev.length ? prev : [createSession({ id: activeId })];
        return list.map((session) => (session.id === activeId ? mutator(session) : session));
      });
    },
    [activeId],
  );

  const startNewChat = () => {
    const session = createSession();
    setSessions((prev) => [session, ...prev]);
    setActiveId(session.id);
    setDraft('');
    setError('');
    setSessionsOpen(false);
  };

  const deleteSession = (id: string) => {
    setSessions((prev) => {
      const next = prev.filter((session) => session.id !== id);
      if (!next.length) {
        const fresh = createSession();
        setActiveId(fresh.id);
        return [fresh];
      }
      if (id === activeId) setActiveId(next[0].id);
      return next;
    });
  };

  const send = async (text: string) => {
    const message = text.trim();
    if (!message || busy || !active) return;
    setError('');
    setBusy(true);
    const userEntry: ChatEntry = { id: newId('u'), role: 'user', text: message };
    const nextEntries = [...entries, userEntry];
    updateActive((session) => ({
      ...session,
      title: session.entries.length === 0 ? titleFromEntries(nextEntries) : session.title,
      updatedAt: Date.now(),
      entries: nextEntries,
    }));
    setDraft('');
    setSessionsOpen(false);
    try {
      const messages = buildAgentHistory(nextEntries);
      const result = await api.glossaryAgentChat(messages);
      const assistantEntry: ChatEntry = { id: newId('a'), role: 'assistant', result };
      updateActive((session) => ({
        ...session,
        updatedAt: Date.now(),
        entries: [...session.entries, assistantEntry],
      }));
    } catch (err) {
      setError((err as Error).message || 'Could not reach the glossary service.');
      // Roll back the unanswered user turn so history stays alternating.
      updateActive((session) => ({
        ...session,
        updatedAt: Date.now(),
        entries: session.entries.filter((entry) => entry.id !== userEntry.id),
        title:
          session.entries.filter((entry) => entry.id !== userEntry.id).length === 0
            ? 'New chat'
            : session.title,
      }));
    } finally {
      setBusy(false);
    }
  };

  const onSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    void send(draft);
  };

  return (
    <div className="glossary-page">
      <aside className={`glossary-sessions ${sessionsOpen ? 'is-open' : ''}`} aria-label="Chat sessions">
        <div className="glossary-sessions-head">
          <strong>Chats</strong>
          <button type="button" className="glossary-new-chat" onClick={startNewChat}>
            New chat
          </button>
        </div>
        <ul className="glossary-session-list">
          {sessions.map((session) => (
            <li key={session.id}>
              <button
                type="button"
                className={session.id === activeId ? 'is-active' : undefined}
                onClick={() => {
                  setActiveId(session.id);
                  setSessionsOpen(false);
                }}
              >
                <span>{session.title}</span>
                <small>{new Date(session.updatedAt).toLocaleDateString()}</small>
              </button>
              <button
                type="button"
                className="glossary-session-delete"
                aria-label={`Delete ${session.title}`}
                onClick={() => deleteSession(session.id)}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      </aside>

      <section className="glossary-workspace">
        <header className="glossary-topbar">
          <button
            type="button"
            className="glossary-sessions-toggle"
            aria-expanded={sessionsOpen}
            onClick={() => setSessionsOpen((open) => !open)}
          >
            Chats
          </button>
          <div className="glossary-topbar-copy">
            <h1>Glossary</h1>
            <p>Educational definitions — not investment advice. Varsity © Zerodha.</p>
          </div>
          <button type="button" className="glossary-new-chat glossary-new-chat-top" onClick={startNewChat}>
            New chat
          </button>
        </header>

        <div className="glossary-chat-log" ref={logRef} aria-live="polite">
          {!entries.length ? (
            <div className="glossary-chat-empty">
              <h2>Start a glossary chat</h2>
              <p>Ask for a plain-English definition, compare two terms, or explore how concepts relate.</p>
              <SuggestionRow busy={busy} onPick={(prompt) => void send(prompt)} />
            </div>
          ) : (
            <div className="glossary-thread">
              {entries.map((entry) =>
                entry.role === 'user' ? (
                  <article key={entry.id} className="glossary-msg glossary-msg-user">
                    <div className="glossary-msg-meta">
                      <span className="glossary-msg-role">You</span>
                    </div>
                    <p>{entry.text}</p>
                  </article>
                ) : (
                  <AssistantMessage key={entry.id} result={entry.result} />
                ),
              )}
              {busy ? (
                <div className="glossary-pending" aria-live="polite">
                  <span className="glossary-pending-dots" aria-hidden="true">
                    <i />
                    <i />
                    <i />
                  </span>
                  Looking that up…
                </div>
              ) : null}
            </div>
          )}
        </div>

        {error ? <p className="glossary-chat-error">{error}</p> : null}

        <div className="glossary-composer">
          {entries.length ? <SuggestionRow busy={busy} onPick={(prompt) => void send(prompt)} /> : null}
          <form className="glossary-chat-form" onSubmit={onSubmit}>
            <label className="glossary-chat-field">
              <span className="visually-hidden">Your question</span>
              <input
                type="text"
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                placeholder="Message Glossary…"
                disabled={busy}
                autoComplete="off"
              />
            </label>
            <button type="submit" className="glossary-send" disabled={busy || !draft.trim()}>
              Send
            </button>
          </form>
          {terms.data?.length ? (
            <p className="glossary-chat-footnote">
              {terms.data.length} curated seed terms · chats stay in this browser
            </p>
          ) : null}
        </div>
      </section>

      {sessionsOpen ? (
        <button
          type="button"
          className="glossary-sessions-backdrop"
          aria-label="Close chats"
          onClick={() => setSessionsOpen(false)}
        />
      ) : null}
    </div>
  );
}
