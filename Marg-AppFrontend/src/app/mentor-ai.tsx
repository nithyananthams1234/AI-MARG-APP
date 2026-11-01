import { useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { AgentPanel } from '@/components/mentor-ai/agent-panel';
import { useLookups } from '@/components/mentor-ai/lookups';
import { Proposals } from '@/components/mentor-ai/proposals';
import { TeacherMessageForm } from '@/components/mentor-ai/teacher-message-form';
import { PageHeader, SectionTitle, pageStyles } from '@/components/reports/page-chrome';
import { Button, Card, StatusBadge } from '@/components/ui/states';
import { MargColors as C } from '@/constants/theme';
import { useMentorAiStatus } from '@/hooks/api';
import { obj, str } from '@/components/mentor-ai/facts';

function StatusCard() {
  const status = useMentorAiStatus();
  const s = status.data;
  const checks = obj(obj(s?.details).checks);
  const aiProvider = str(obj(checks.ai_provider).status);
  let badge: { key: string; label: string };
  if (status.isLoading && !s) badge = { key: 'pending', label: 'Checking…' };
  else if (!s) badge = { key: 'rejected', label: 'Status unknown' };
  else badge = s.available ? { key: 'completed', label: 'Available' } : { key: 'rejected', label: 'Unavailable' };

  return (
    <Card>
      <View style={pageStyles.rowBetween}>
        <Text style={[pageStyles.itemTitle, { flex: 1 }]}>Mentor AI Assistant</Text>
        <StatusBadge status={badge.key} label={badge.label} />
      </View>
      <Text style={[pageStyles.muted, { marginTop: 4 }]}>
        Plans and analyses are computed from your recorded visits, tasks and follow-ups. When enabled, an AI adds a short narrative, always
        labelled as AI. Suggested actions change nothing until you approve them.
      </Text>
      {s?.available && aiProvider && aiProvider !== 'ok' && aiProvider !== 'ready' ? (
        <Text style={[pageStyles.muted, { marginTop: 4 }]}>AI narrative: {aiProvider === 'disabled' ? 'turned off on the server' : aiProvider}. Computed analysis is available.</Text>
      ) : null}
      {!s && status.error ? <Button label="Check again" variant="secondary" onPress={() => void status.refetch()} style={{ marginTop: 8, alignSelf: 'flex-start' }} /> : null}
    </Card>
  );
}

export default function MentorAiScreen() {
  const qc = useQueryClient();
  const lookups = useLookups();
  const status = useMentorAiStatus();
  const [refreshing, setRefreshing] = useState(false);

  const refresh = async () => {
    setRefreshing(true);
    try {
      await Promise.all([
        qc.invalidateQueries({ queryKey: ['mentor-ai'] }),
        qc.invalidateQueries({ queryKey: ['follow-ups'] }),
        qc.invalidateQueries({ queryKey: ['visits'] }),
        qc.invalidateQueries({ queryKey: ['tasks'] }),
      ]);
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <SafeAreaView style={pageStyles.safeArea} edges={['top']}>
      <ScrollView
        contentContainerStyle={pageStyles.content}
        keyboardShouldPersistTaps="handled"
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => void refresh()} tintColor={C.teal} />}
      >
        <PageHeader title="Mentor AI" subtitle="Planning and prioritisation from your records" right={<Text style={styles.icon}>✦</Text>} />
        <StatusCard />

        <SectionTitle title="Analyses" />
        <AgentPanel lookups={lookups} available={status.data?.available} />

        <SectionTitle title="Teacher message" />
        <TeacherMessageForm lookups={lookups} />

        <SectionTitle title="Suggested actions" />
        <Proposals lookups={lookups} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  icon: { color: C.teal, fontSize: 24, fontWeight: '800' },
});
