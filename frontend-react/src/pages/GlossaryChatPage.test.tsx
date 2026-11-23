import React from 'react';
import { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { AssistantMessage, EvidencePanel } from './glossaryChatUi';
import type { GlossaryAgentChatResult, GlossaryCitation } from '../api';

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

describe('Glossary chat UI pieces', () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    container.remove();
  });

  it('renders prose answer, mode note, and evidence accordion', () => {
    const result: GlossaryAgentChatResult = {
      assistant_message: 'An **IPO** is a first sale of shares to the public.',
      mode: 'multi_agent',
      citations: [
        {
          module: 1,
          chapter: 'The IPO Markets',
          url: 'https://zerodha.com/varsity/chapter/ipo/',
          term: 'IPO',
          excerpt: 'An IPO is the first sale of stock by a private company.',
        },
      ],
    };

    act(() => {
      root.render(<AssistantMessage result={result} />);
    });

    expect(container.textContent).toContain('IPO');
    expect(container.textContent).toContain('Local corpus');
    expect(container.querySelector('.glossary-evidence')).not.toBeNull();
    expect(container.textContent).toContain('Sources');
    expect(container.textContent).toContain('The IPO Markets');
  });

  it('shows refusal label and hides mode note', () => {
    const result: GlossaryAgentChatResult = {
      assistant_message: 'This glossary explains investing terms only.',
      mode: 'multi_agent',
      refusal: { category: 'advice', reason: 'This glossary explains investing terms only.' },
    };

    act(() => {
      root.render(<AssistantMessage result={result} />);
    });

    expect(container.textContent).toContain('No investment advice');
    expect(container.textContent).not.toContain('Local corpus');
    expect(container.querySelector('.glossary-msg-refusal')).not.toBeNull();
  });

  it('renders evidence excerpts in the panel', () => {
    const citations: GlossaryCitation[] = [
      {
        module: 9,
        chapter: 'NAV',
        url: 'https://zerodha.com/varsity/chapter/nav/',
        term: 'NAV',
        excerpt: 'NAV is the per-unit market value of a mutual fund scheme.',
      },
    ];

    act(() => {
      root.render(<EvidencePanel citations={citations} />);
    });

    expect(container.textContent).toContain('NAV');
    expect(container.textContent).toContain('per-unit market value');
    expect(container.querySelector('a.glossary-evidence-link')?.getAttribute('href')).toContain(
      'varsity/chapter/nav',
    );
  });
});
