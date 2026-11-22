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
    .replace(/^\s*[-*]\s+[“"'].+[”"']\s*[—–-].+$/gm, '')
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
        return <p key={index}>{renderInlineEmphasis(block.replace(/\n/g, ' '))}</p>;
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
  return out.slice(0, 4);
}

function modeLabel(mode: GlossaryAgentChatResult['mode']): string | null {
  if (mode === 'fallback') return 'Seed lookup';
  if (mode === 'multi_agent') return 'Local corpus';
  if (mode === 'agent') return 'Seed agent';
  return null;
}

function AssistantMessage({ result }: { result: GlossaryAgentChatResult }) {
  const refusal = result.refusal;
  const citations = result.citations?.length ? dedupeCitations(result.citations) : [];
  const mode = modeLabel(result.mode);

  return (
    <article
      className={
        refusal
          ? 'glossary-msg glossary-msg-assistant glossary-msg-refusal'
          : 'glossary-msg glossary-msg-assistant'
      }
    >
      <div className="glossary-msg-meta">
        <span className="glossary-msg-role">{refusal ? 'Notice' : 'Assistant'}</span>
        {mode && !refusal ? <span className="glossary-msg-mode">{mode}</span> : null}
      </div>
      {refusal ? (
        <p className="glossary-refusal-label">
          {refusal.category === 'advice' ? 'No investment advice' : 'Definitions only'}
        </p>
      ) : null}
      <Prose text={result.assistant_message} />
      {citations.length ? <EvidencePanel citations={citations} /> : null}
    </article>
  );
}

function EvidencePanel({ citations }: { citations: GlossaryCitation[] }) {
  return (
    <details className="glossary-evidence">
      <summary>
        <span>Sources</span>
        <span className="glossary-evidence-count">{citations.length}</span>
      </summary>
      <ul className="glossary-evidence-list">
        {citations.map((source) => (
          <li key={`${source.module}-${source.chapter}-${source.url}-${source.chunk_id ?? source.term ?? ''}`}>
            <div className="glossary-evidence-row">
              <div className="glossary-evidence-meta">
                {source.term ? <span className="glossary-evidence-term">{source.term}</span> : null}
                <span>
                  Module {source.module}
                  {source.chapter ? ` · ${source.chapter}` : ''}
                </span>
              </div>
              {source.url ? (
                <a className="glossary-evidence-link" href={source.url} target="_blank" rel="noreferrer">
                  Varsity
                </a>
              ) : null}
            </div>
            {source.excerpt ? <p className="glossary-evidence-excerpt">{source.excerpt}</p> : null}
          </li>
        ))}
      </ul>
    </details>
  );
}

function SuggestionRow({
  busy,
  onPick,
}: {
  busy: boolean;
  onPick: (prompt: string) => void;
}) {
  return (
    <div className="glossary-suggestions" aria-label="Suggested questions">
      {SUGGESTION_PROMPTS.map((prompt) => (
        <button key={prompt} type="button" onClick={() => onPick(prompt)} disabled={busy}>
          {prompt}
        </button>
      ))}
    </div>
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
    <div className="glossary-page">
      <PageHeader
        title="Glossary"
        subtitle="Ask investing terms in plain language. Answers stay educational — not advice."
      />

      <section className="glossary-shell">
        <div className="glossary-banner" role="note">
          <span className="glossary-banner-kicker">Educational POC</span>
          <span>
            Definitions only. Corpus stays on your machine. Varsity materials © Zerodha.
          </span>
        </div>

        <div className="glossary-chat-log" ref={logRef} aria-live="polite">
          {!entries.length ? (
            <div className="glossary-chat-empty">
              <h2>Start with a term</h2>
              <p>Compare ideas, ask for a plain-English definition, or explore how concepts relate.</p>
              <SuggestionRow busy={busy} onPick={(prompt) => void send(prompt)} />
            </div>
          ) : (
            entries.map((entry) =>
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
            )
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
                placeholder="Ask about an investing term…"
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
              {terms.data.length} curated seed terms · deeper reading opens on Varsity
            </p>
          ) : null}
        </div>
      </section>
    </div>
  );
}
