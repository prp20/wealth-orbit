import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { api, GlossaryChatResult } from '../api';
import PageHeader from '../components/PageHeader';

type ChatEntry =
  | { id: string; role: 'user'; text: string }
  | { id: string; role: 'assistant'; result: GlossaryChatResult };

function refusalLabel(category: 'advice' | 'dump') {
  if (category === 'advice') return 'No investment advice';
  return 'Definitions only';
}

function AssistantMessage({ result }: { result: GlossaryChatResult }) {
  if (result.kind === 'match') {
    return (
      <article className="glossary-chat-bubble glossary-chat-bubble-assistant">
        <h3 className="glossary-term-title">{result.term}</h3>
        <p className="glossary-definition">{result.definition}</p>
        {result.sources?.length ? (
          <>
            <h4 className="glossary-sources-heading">Further reading (Zerodha Varsity)</h4>
            <ul className="glossary-sources">
              {result.sources.map((source) => (
                <li key={`${source.module}-${source.chapter}-${source.url}`}>
                  <a href={source.url} target="_blank" rel="noreferrer">
                    Module {source.module} · {source.chapter}
                  </a>
                </li>
              ))}
            </ul>
          </>
        ) : null}
      </article>
    );
  }

  if (result.kind === 'refusal') {
    return (
      <article className="glossary-chat-bubble glossary-chat-bubble-assistant glossary-chat-refusal">
        <p className="glossary-refusal-label">{refusalLabel(result.refusal_category)}</p>
        <p>{result.refusal_reason}</p>
      </article>
    );
  }

  return (
    <article className="glossary-chat-bubble glossary-chat-bubble-assistant glossary-chat-unknown">
      <p className="glossary-refusal-label">Term not found</p>
      <p>
        No matching term in the glossary seed. Try a shorter question (for example, &ldquo;What is
        IPO?&rdquo;) or pick a known term from the list below.
      </p>
    </article>
  );
}

export default function GlossaryChatPage() {
  const [entries, setEntries] = React.useState<ChatEntry[]>([]);
  const [draft, setDraft] = React.useState('');
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState('');
  const logRef = React.useRef<HTMLDivElement>(null);
  const terms = useQuery({ queryKey: ['glossary-terms'], queryFn: api.glossaryTerms, staleTime: 60 * 60 * 1000 });

  const sampleTerms = React.useMemo(() => {
    const rows = terms.data || [];
    if (!rows.length) return [];
    return rows.slice(0, 12).map((row) => row.term);
  }, [terms.data]);

  React.useEffect(() => {
    const node = logRef.current;
    if (!node) return;
    node.scrollTop = node.scrollHeight;
  }, [entries.length, busy]);

  const send = async (text: string) => {
    const message = text.trim();
    if (!message || busy) return;
    setError('');
    setBusy(true);
    const userId = `u-${Date.now()}`;
    setEntries((prev) => [...prev, { id: userId, role: 'user', text: message }]);
    setDraft('');
    try {
      const result = await api.glossaryChat(message);
      setEntries((prev) => [...prev, { id: `a-${Date.now()}`, role: 'assistant', result }]);
    } catch (err) {
      setError((err as Error).message || 'Could not reach the glossary service.');
    } finally {
      setBusy(false);
    }
  };

  const onSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    void send(draft);
  };

  const askSample = (term: string) => {
    void send(`What is ${term}?`);
  };

  return (
    <>
      <PageHeader
        title="Glossary"
        subtitle="Short definitions of investing terms with Varsity chapter links. This page explains terminology only—it does not give buy, sell, switch, or personalized advice."
      />

      <section className="panel glossary-chat-panel">
        <div className="glossary-chat-log" ref={logRef} aria-live="polite">
          {!entries.length ? (
            <div className="glossary-chat-empty">
              <p>Ask about a term, for example &ldquo;What is ETF?&rdquo; or &ldquo;meaning of SIP&rdquo;.</p>
              {sampleTerms.length ? (
                <div className="glossary-sample-terms">
                  <span>Try:</span>
                  {sampleTerms.map((term) => (
                    <button key={term} type="button" onClick={() => askSample(term)} disabled={busy}>
                      {term}
                    </button>
                  ))}
                </div>
              ) : terms.isLoading ? (
                <p className="panel-subtitle">Loading term list…</p>
              ) : null}
            </div>
          ) : (
            entries.map((entry) =>
              entry.role === 'user' ? (
                <article key={entry.id} className="glossary-chat-bubble glossary-chat-bubble-user">
                  <p>{entry.text}</p>
                </article>
              ) : (
                <AssistantMessage key={entry.id} result={entry.result} />
              ),
            )
          )}
          {busy ? <p className="glossary-chat-pending">Looking up definition…</p> : null}
        </div>

        {error ? <p className="glossary-chat-error">{error}</p> : null}

        <form className="glossary-chat-form" onSubmit={onSubmit}>
          <label className="glossary-chat-field">
            <span className="visually-hidden">Your question</span>
            <input
              type="text"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder="Ask about an investing term…"
              disabled={busy}
              autoComplete="off"
            />
          </label>
          <button type="submit" className="primary-button" disabled={busy || !draft.trim()}>
            Send
          </button>
        </form>
      </section>

      {sampleTerms.length ? (
        <p className="panel-subtitle glossary-chat-footnote">
          {terms.data?.length ?? 0} curated terms in the seed. Full Varsity chapters open on zerodha.com.
        </p>
      ) : null}
    </>
  );
}