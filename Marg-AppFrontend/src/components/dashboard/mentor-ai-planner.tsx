import { Pressable, StyleSheet, Text, View } from 'react-native';

import { Button, Card, InlineNotice, StatusBadge } from '@/components/ui/states';
import { MargColors as C } from '@/constants/theme';
import { useMentorAiStatus } from '@/hooks/api';

export function MentorAiPlanner({ onOpenFullAssistant }: { onOpenFullAssistant: () => void }) {
  const status = useMentorAiStatus();

  const statusLabel = status.isLoading && !status.data
    ? 'Checking'
    : status.data?.available
      ? 'Available'
      : status.data
        ? 'Unavailable'
        : 'Status unknown';
  const statusKey = status.data?.available ? 'completed' : status.data ? 'rejected' : 'pending';

  return (
    <Card style={styles.card}>
      <View style={styles.hero}>
        <View style={styles.heroRow}>
          <View style={styles.iconWrap} accessibilityElementsHidden>
            <Text style={styles.icon}>✦</Text>
            <Text style={styles.iconAccent}>✧</Text>
          </View>
          <View style={styles.heroCopy}>
            <Text style={styles.title} accessibilityRole="header">Mentor AI Planner</Text>
            <Text style={styles.description}>
              Plan, prioritise and organise your mentoring activities with AI assistance.
            </Text>
          </View>
        </View>
      </View>

      <View style={styles.content}>
        <View style={styles.statusRow}>
          <Text style={styles.statusCaption}>Service status</Text>
          <StatusBadge status={statusKey} label={statusLabel} />
        </View>
        {status.data?.available === false ? (
          <InlineNotice tone="warning" text="The Mentor AI service reports that it is unavailable. Existing records remain available; new analysis may fail." />
        ) : null}
        {!status.data && status.error ? (
          <View>
            <InlineNotice tone="warning" text="Service status could not be confirmed." />
            <Button
              label="Check service status"
              variant="secondary"
              onPress={() => void status.refetch()}
              loading={status.isFetching}
              style={{ marginTop: 8, alignSelf: 'flex-start' }}
            />
          </View>
        ) : null}
        <Pressable
          onPress={onOpenFullAssistant}
          accessibilityRole="link"
          accessibilityLabel="Open Mentor AI Planner"
          style={({ pressed }) => [styles.fullLink, pressed && styles.pressed]}
        >
          <Text style={styles.fullLinkText}>Open Mentor AI Planner</Text>
          <Text style={styles.arrow} accessibilityElementsHidden>→</Text>
        </Pressable>
      </View>
    </Card>
  );
}

const styles = StyleSheet.create({
  card: { padding: 0, overflow: 'hidden', borderRadius: 20 },
  hero: { backgroundColor: C.navy, padding: 18 },
  heroRow: { flexDirection: 'row', alignItems: 'center', gap: 14 },
  iconWrap: {
    width: 52,
    height: 52,
    borderRadius: 16,
    backgroundColor: C.navyLight,
    borderWidth: 1,
    borderColor: '#3B5D7E',
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
  },
  icon: { color: '#FFFFFF', fontSize: 29, lineHeight: 34, fontWeight: '700' },
  iconAccent: { position: 'absolute', right: 7, bottom: 5, color: '#56D4C7', fontSize: 13 },
  heroCopy: { flex: 1, minWidth: 0 },
  title: { color: '#FFFFFF', fontSize: 19, lineHeight: 25, fontWeight: '800' },
  description: { color: '#DCE8F4', fontSize: 13, lineHeight: 19, marginTop: 5 },
  content: { padding: 16 },
  statusRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 },
  statusCaption: { color: C.secondaryText, fontSize: 12, fontWeight: '600' },
  fullLink: {
    minHeight: 50,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
    marginTop: 2,
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderRadius: 14,
    backgroundColor: C.tealDark,
  },
  fullLinkText: { color: '#FFFFFF', fontSize: 14, fontWeight: '700', flexShrink: 1 },
  arrow: { color: '#FFFFFF', fontSize: 23, lineHeight: 25, fontWeight: '500' },
  pressed: { opacity: 0.86 },
});
