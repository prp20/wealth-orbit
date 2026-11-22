import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { api, GlossaryAgentChatMessage, GlossaryAgentChatResult, GlossaryCitation } from '../api';
import PageHeader from '../components/PageHeader';

const SUGGESTION_PROMPTS = ['What is an IPO?', 'ROE vs ROCE', 'What is NAV?'] as const;

type ChatEntry =
  | { id: string; role: 'user'; text: string }
  | { id: string; role: 'assistant'; result: GlossaryAgentChatResult };

function cleanProse(text: string): string {
  return text
    .replace(/【[^】]+】/g, '')
    .replace(/\[[\w:.-]{1,40}\]/g, '')
    .replace(/^#{1,6}\s+/gm, '')
    .replace(/[ \t]+\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

function renderInlineEmphasis(text: string): React.ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*)/g);
  return parts.map((part, index) => {
    if (part.startsWith('**') && part.endsWith('**') && part.length > 4) {
      return <strong key={index}>{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith('*') && part.endsWith('*') && part.length > 2 && !part.startsWith('**')) {
      return <em key={index}>{part.slice(1, -1)}</em>;
    }
    return <React.Fragment key={index}>{part}</React.Fragment>;
  });
}

function Prose({ text }: { text: string }) {
  const cleaned = cleanProse(text);
  const blocks = cleaned.split(/\n{2,}/).filter(Boolean);
  return (
    <div className="glossary-agent-prose">
      {blocks.map((block, index) => {
        const lines = block.split('\n');
        const isList = lines.every((line) => /^\s*\d+\.\s+/.test(line) || /^\s*[-*]\s+/.test(line));
        if (isList) {
          const ordered = lines.every((line) => /^\s*\d+\.\s+/.test(line));
          const ListTag = ordered ? 'ol' : 'ul';
          return (
            <ListTag key={index} className="glossary-agent-list">
              {lines.map((line, lineIndex) => (
                <li key={lineIndex}>
                  {renderInlineEmphasis(line.replace(/^\s*(?:\d+\.|[-*])\s+/, ''))}
                </li>
              ))}
            </ListTag>
          );
        }
        return (
          <p key={index}>{renderInlineEmphasis(block.replace(/\n/g, ' '))}</p>
        );
      })}
    </div>
  );
}

function dedupeCitations(citations: GlossaryCitation[]): GlossaryCitation[] {
  const seen = new Set<string>();
  const out: GlossaryCitation[] = [];
  for (const source of citations) {
    const key = `${source.module}|${source.chapter}|${source.url}|${source.term ?? ''}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(source);
  }
  return out.slice(0, 6);
}

function AssistantMessage({ result }: { result: GlossaryAgentChatResult }) {
  const refusal = result.refusal;
  const bubbleClass = refusal
    ? 'glossary-chat-bubble glossary-chat-bubble-assistant glossary-chat-refusal'
    : 'glossary-chat-bubble glossary-chat-bubble-assistant';
  const citations = result.citations?.length ? dedupeCitations(result.citations) : [];

  return (
    <article className={bubbleClass}>
      {refusal ? (
        <p className="glossary-refusal-label">
          {refusal.category === 'advice' ? 'No investment advice' : 'Definitions only'}
        </p>
      ) : null}
      <Prose text={result.assistant_message} />
      {result.mode === 'fallback' ? (
        <p className="glossary-chat-mode-note">AI chat is offline — using seed lookup.</p>
      ) : null}
      {result.mode === 'multi_agent' ? (
        <p className="glossary-chat-mode-note">Answered with local corpus RAG (POC).</p>
      ) : null}
      {citations.length ? <EvidencePanel citations={citations} /> : null}
    </article>
  );
}

function EvidencePanel({ citations }: { citations: GlossaryCitation[] }) {
  return (
    <details className="glossary-evidence">
      <summary>Evidence ({citations.length})</summary>
      <ul className="glossary-evidence-list">
        {citations.map((source) => (
          <li key={`${source.module}-${source.chapter}-${source.url}-${source.chunk_id ?? source.term ?? ''}`}>
            <div className="glossary-evidence-meta">
              {source.term ? <strong>{source.term}</strong> : null}
              {source.term ? ' · ' : null}
              Module {source.module}
              {source.chapter ? ` · ${source.chapter}` : ''}
              {source.url ? (
                <>
                  {' · '}
                  <a href={source.url} target="_blank" rel="noreferrer">
                    Varsity
                  </a>
                </>
              ) : null}
            </div>
            {source.excerpt ? <p className="glossary-evidence-excerpt">{source.excerpt}</p> : null}
          </li>
        ))}
      </ul>
    </details>
  );
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
  const [entries, setEntries] = React.useState<ChatEntry[]>([]);
  const [draft, setDraft] = React.useState('');
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState('');
  const logRef = React.useRef<HTMLDivElement>(null);
  const terms = useQuery({ queryKey: ['glossary-terms'], queryFn: api.glossaryTerms, staleTime: 60 * 60 * 1000 });

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
    const nextEntries: ChatEntry[] = [...entries, { id: userId, role: 'user', text: message }];
    setEntries(nextEntries);
    setDraft('');
    try {
      const messages = buildAgentHistory(nextEntries);
      const result = await api.glossaryAgentChat(messages);
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

  return (
    <>
      <PageHeader
        title="Glossary"
        subtitle="Multi-turn chat for investing terminology. Prose answers with optional local corpus evidence."
      />

      <section className="panel glossary-chat-panel">
        <div className="glossary-chat-banner" role="note">
          POC educational assistant — not advice; corpus stays local. Explains terms only (no buy/sell/switch
          picks). Varsity © Zerodha.
        </div>

        <div className="glossary-chat-log" ref={logRef} aria-live="polite">
          {!entries.length ? (
            <div className="glossary-chat-empty">
              <p>Ask about a term or compare concepts in plain language.</p>
              <div className="glossary-suggestion-chips">
                <span>Suggestions:</span>
                {SUGGESTION_PROMPTS.map((prompt) => (
                  <button key={prompt} type="button" onClick={() => send(prompt)} disabled={busy}>
                    {prompt}
                  </button>
                ))}
              </div>
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
          {busy ? <p className="glossary-chat-pending">Thinking…</p> : null}
        </div>

        {error ? <p className="glossary-chat-error">{error}</p> : null}

        {entries.length ? (
          <div className="glossary-suggestion-chips glossary-suggestion-chips-inline">
            {SUGGESTION_PROMPTS.map((prompt) => (
              <button key={prompt} type="button" onClick={() => send(prompt)} disabled={busy}>
                {prompt}
              </button>
            ))}
          </div>
        ) : null}

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

      {terms.data?.length ? (
        <p className="panel-subtitle glossary-chat-footnote">
          {terms.data.length} curated terms in the seed. Full Varsity chapters open on zerodha.com.
        </p>
      ) : terms.isLoading ? (
        <p className="panel-subtitle glossary-chat-footnote">Loading term list…</p>
      ) : null}
    </>
  );
}
