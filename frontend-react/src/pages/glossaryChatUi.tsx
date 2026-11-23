import React from 'react';
import type { GlossaryAgentChatResult, GlossaryCitation } from '../api';

export const SUGGESTION_PROMPTS = ['What is an IPO?', 'ROE vs ROCE', 'What is NAV?'] as const;

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

export function Prose({ text }: { text: string }) {
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

export function EvidencePanel({ citations }: { citations: GlossaryCitation[] }) {
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

export function AssistantMessage({ result }: { result: GlossaryAgentChatResult }) {
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

export function SuggestionRow({
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
