/** One question/answer exchange with the Classroom Coach. */
import { ActivityIndicator, StyleSheet, Text, View } from 'react-native';

import { pageStyles } from '@/components/reports/page-chrome';
import { Button, InlineNotice } from '@/components/ui/states';
import { MargColors as C } from '@/constants/theme';
import type { CoachChatResponse } from '@/lib/api/generated';

import { AnswerText } from './answer-text';

export interface Exchange {
  id: string;
  question: string;
  contextLabel?: string;
  startedAt: number;
  status: 'pending' | 'done' | 'error';
  response?: CoachChatResponse;
  error?: { message: string; status: number | null };
}

function Thinking() {
  return (
    <View style={styles.thinking} accessibilityRole="progressbar" accessibilityLabel="The Coach is preparing an answer" accessibilityLiveRegion="polite">
      <ActivityIndicator color={C.teal} />
      <View style={{ flex: 1 }}>
        <Text style={styles.thinkingTitle}>Coach is thinking…</Text>
        <Text style={pageStyles.muted}>Searching the knowledge base and drafting an answer.</Text>
      </View>
    </View>
  );
}

export function ExchangeCard({
  exchange,
  onRetry,
  onShare,
  retryDisabled,
}: {
  exchange: Exchange;
  onRetry: () => void;
  onShare: (r: CoachChatResponse) => void;
  retryDisabled?: boolean;
}) {
  const { response: r } = exchange;
  return (
    <View style={styles.wrap}>
      <View style={styles.question} accessible accessibilityLabel={`Your question: ${exchange.question}`}>
        <Text style={styles.questionText}>{exchange.question}</Text>
        {exchange.contextLabel ? <Text style={styles.questionContext}>Context: {exchange.contextLabel}</Text> : null}
      </View>

      <View style={styles.answer}>
        <Text style={styles.answerLabel}>Classroom Coach · AI-generated</Text>
        {exchange.status === 'pending' ? <Thinking /> : null}

        {exchange.status === 'error' && exchange.error ? (
          <View accessibilityRole="alert">
            <InlineNotice
              tone="danger"
              text={
                exchange.error.status === 503
                  ? 'The Classroom Coach is unavailable right now. Please try again in a few minutes.'
                  : exchange.error.message
              }
            />
            <Button label="Try again" variant="secondary" onPress={onRetry} disabled={retryDisabled} />
          </View>
        ) : null}

        {r ? (
          <>
            {!r.grounded ? (
              <InlineNotice
                tone="warning"
                text="No relevant passage was found in the MARG knowledge base for this question. Treat this answer as general, unverified guidance and use your own professional judgement."
              />
            ) : null}
            <AnswerText text={r.answer} hideCitations />
            <Text style={styles.disclaimer}>
              AI-generated suggestion{r.model ? ` (${r.model})` : ''}. Not an official MARG guideline; review before using with teachers.
            </Text>
            <Button label="Draft a WhatsApp message from this answer" variant="ghost" onPress={() => onShare(r)} style={{ alignSelf: 'flex-start' }} />
          </>
        ) : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { marginBottom: 16, gap: 8 },
  question: { alignSelf: 'flex-end', maxWidth: '88%', backgroundColor: C.navy, borderRadius: 16, borderBottomRightRadius: 4, padding: 12 },
  questionText: { color: '#FFF', fontSize: 15, lineHeight: 21 },
  questionContext: { color: '#C9D6E6', fontSize: 12, marginTop: 4 },
  answer: { backgroundColor: C.surface, borderRadius: 16, borderTopLeftRadius: 4, borderWidth: 1, borderColor: C.border, padding: 14, gap: 6 },
  answerLabel: { color: C.tealDark, fontSize: 12, fontWeight: '800', marginBottom: 4 },
  thinking: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 6 },
  thinkingTitle: { color: C.navy, fontSize: 14, fontWeight: '700' },
  disclaimer: { color: C.secondaryText, fontSize: 12, marginTop: 10, fontStyle: 'italic' },
});
