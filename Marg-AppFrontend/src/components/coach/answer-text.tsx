/**
 * Renders a Coach answer (markdown-ish plain text) readably: keeps line
 * breaks, shows bullets / numbered items as indented rows, headings in bold,
 * strips **bold** markers and highlights inline citations like [S1].
 */
import { StyleSheet, Text, View } from 'react-native';

import { MargColors as C } from '@/constants/theme';

const CITATION = /(\[S\d+(?:\s*[,;]\s*S?\d+)*\])/g;
const IS_CITATION = /^\[S\d+(?:\s*[,;]\s*S?\d+)*\]$/;

function Inline({ text, style }: { text: string; style?: object }) {
  const parts = text.replace(/\*\*(.+?)\*\*/g, '$1').replace(/__(.+?)__/g, '$1').split(CITATION);
  return (
    <Text style={[styles.text, style]}>
      {parts.map((p, i) =>
        IS_CITATION.test(p) ? (
          <Text key={i} style={styles.citation}>
            {p}
          </Text>
        ) : (
          p
        ),
      )}
    </Text>
  );
}

export function AnswerText({ text, hideCitations = false }: { text: string; hideCitations?: boolean }) {
  const displayText = hideCitations ? text.replace(CITATION, '') : text;
  const lines = displayText.replace(/\r\n/g, '\n').split('\n');
  return (
    <View style={{ gap: 4 }}>
      {lines.map((raw, i) => {
        const line = raw.trimEnd();
        if (!line.trim()) return <View key={i} style={{ height: 6 }} />;
        const heading = /^\s*#{1,6}\s+(.*)$/.exec(line);
        if (heading) return <Inline key={i} text={heading[1]} style={styles.heading} />;
        const bullet = /^(\s*)[-*•]\s+(.*)$/.exec(line);
        const numbered = /^(\s*)(\d+[.)])\s+(.*)$/.exec(line);
        if (bullet || numbered) {
          const indent = Math.min(3, Math.floor(((bullet ?? numbered)![1].length || 0) / 2));
          return (
            <View key={i} style={[styles.listRow, { paddingLeft: indent * 14 }]}>
              <Text style={styles.marker}>{bullet ? '•' : numbered![2]}</Text>
              <View style={{ flex: 1 }}>
                <Inline text={bullet ? bullet[2] : numbered![3]} />
              </View>
            </View>
          );
        }
        return <Inline key={i} text={line} />;
      })}
    </View>
  );
}

/** Answer text without citation markers / markdown (for a teacher message draft). */
export function plainAnswer(text: string) {
  return text
    .replace(CITATION, '')
    .replace(/\*\*(.+?)\*\*/g, '$1')
    .replace(/^\s*#{1,6}\s+/gm, '')
    .replace(/[ \t]+\n/g, '\n')
    .replace(/ {2,}/g, ' ')
    .trim();
}

const styles = StyleSheet.create({
  text: { color: C.text, fontSize: 15, lineHeight: 22 },
  heading: { color: C.navy, fontWeight: '800', marginTop: 4 },
  citation: { color: C.tealDark, fontWeight: '700', fontSize: 13 },
  listRow: { flexDirection: 'row', gap: 8 },
  marker: { color: C.tealDark, fontSize: 15, lineHeight: 22, fontWeight: '700', minWidth: 14 },
});
