/** Sources returned by the Coach, shown exactly as returned ([S1]..[Sn]). */
import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { MargColors as C } from '@/constants/theme';
import type { CoachSource } from '@/lib/api/generated';

function SourceRow({ source, index }: { source: CoachSource; index: number }) {
  const [open, setOpen] = useState(false);
  const title = source.title || source.document;
  const hasExcerpt = !!source.excerpt?.trim();
  return (
    <View style={styles.source}>
      <Pressable
        onPress={() => hasExcerpt && setOpen((o) => !o)}
        disabled={!hasExcerpt}
        accessibilityRole="button"
        accessibilityState={{ expanded: open, disabled: !hasExcerpt }}
        accessibilityLabel={`Source S${index + 1}: ${title}, page ${source.page}${hasExcerpt ? (open ? '. Hide excerpt' : '. Show excerpt') : ''}`}
        style={styles.sourceHeader}
      >
        <Text style={styles.tag}>S{index + 1}</Text>
        <View style={{ flex: 1 }}>
          <Text style={styles.title}>{title}</Text>
          <Text style={styles.meta}>
            Page {source.page}
            {source.title && source.document !== source.title ? ` · ${source.document}` : ''}
            {source.relevance != null ? ` · relevance ${source.relevance.toFixed(2)}` : ''}
          </Text>
        </View>
        {hasExcerpt ? <Text style={styles.chevron}>{open ? '▴' : '▾'}</Text> : null}
      </Pressable>
      {open && hasExcerpt ? <Text style={styles.excerpt}>“{source.excerpt!.trim()}”</Text> : null}
    </View>
  );
}

export function SourcesList({ sources }: { sources: CoachSource[] }) {
  if (sources.length === 0) return null;
  return (
    <View style={styles.wrap}>
      <Text style={styles.heading}>Sources from the MARG knowledge base</Text>
      {sources.map((s, i) => (
        <SourceRow key={`${s.document}-${s.page}-${i}`} source={s} index={i} />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { marginTop: 12, gap: 6 },
  heading: { color: C.navy, fontSize: 13, fontWeight: '800' },
  source: { backgroundColor: C.inputBackground, borderRadius: 10, borderWidth: 1, borderColor: C.border },
  sourceHeader: { flexDirection: 'row', alignItems: 'center', gap: 10, padding: 10 },
  tag: { color: C.tealDark, fontWeight: '800', fontSize: 12, backgroundColor: '#E8F7F5', borderRadius: 6, paddingHorizontal: 6, paddingVertical: 2 },
  title: { color: C.navy, fontSize: 13, fontWeight: '700' },
  meta: { color: C.secondaryText, fontSize: 12, marginTop: 1 },
  chevron: { color: C.secondaryText, fontSize: 14 },
  excerpt: { color: C.text, fontSize: 13, lineHeight: 19, paddingHorizontal: 12, paddingBottom: 10, fontStyle: 'italic' },
});
