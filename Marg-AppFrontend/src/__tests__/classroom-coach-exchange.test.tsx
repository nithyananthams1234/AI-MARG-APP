import { render } from '@testing-library/react-native';

import { ExchangeCard } from '@/components/coach/exchange-card';

describe('Classroom Coach exchange', () => {
  it('shows the answer without citation labels or source document details', async () => {
    const view = await render(
      <ExchangeCard
        exchange={{
          id: 'exchange-1',
          question: 'How can I teach equivalent fractions?',
          startedAt: Date.now(),
          status: 'done',
          response: {
            question: 'How can I teach equivalent fractions?',
            answer: 'Use fraction strips to compare values. [S1]',
            grounded: true,
            model: 'nvidia/test-model',
            sources: [
              {
                document: 'fractions.pdf',
                title: 'Teaching Fractions',
                page: 4,
                relevance: 0.9,
                excerpt: 'Use concrete fraction strips.',
              },
            ],
          },
        }}
        onRetry={jest.fn()}
        onShare={jest.fn()}
      />,
    );

    expect(view.getByText(/Use fraction strips to compare values\./)).toBeTruthy();
    expect(view.queryByText('[S1]')).toBeNull();
    expect(view.queryByText('fractions.pdf')).toBeNull();
    expect(view.queryByText('Teaching Fractions')).toBeNull();
    expect(view.queryByText('Use concrete fraction strips.')).toBeNull();
    expect(view.queryByText('Sources from the MARG knowledge base')).toBeNull();
  });

  it('shows the thinking message without an elapsed-seconds counter', async () => {
    const view = await render(
      <ExchangeCard
        exchange={{
          id: 'exchange-pending',
          question: 'How can I teach equivalent fractions?',
          startedAt: Date.now(),
          status: 'pending',
        }}
        onRetry={jest.fn()}
        onShare={jest.fn()}
      />,
    );

    expect(view.getByText('Coach is thinking…')).toBeTruthy();
    expect(view.queryByText(/\d+s$/)).toBeNull();
    expect(view.getByText('Searching the knowledge base and drafting an answer.')).toBeTruthy();
  });
});
