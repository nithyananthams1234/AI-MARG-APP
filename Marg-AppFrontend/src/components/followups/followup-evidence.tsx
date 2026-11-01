import * as ImagePicker from 'expo-image-picker';
import { useState } from 'react';
import { ActivityIndicator, Pressable, Text, View } from 'react-native';

import { InlineNotice } from '@/components/ui/states';
import { MargColors as C } from '@/constants/theme';
import { useEvidence, useUploadEvidence } from '@/hooks/api';
import { formatDateTime } from '@/lib/format';
import { assetToUpload } from '@/lib/upload';

import { fuStyles as styles } from './followup-styles';
import { formatBytes } from './followup-utils';

/** Evidence files attached to a follow-up, with photo upload (JPEG/PNG). */
export function FollowUpEvidence({ followUpId, canUpload }: { followUpId: string; canUpload: boolean }) {
  const evidence = useEvidence({ follow_up_id: followUpId });
  const upload = useUploadEvidence();
  const [message, setMessage] = useState<{ tone: 'success' | 'danger'; text: string } | null>(null);

  const pickAndUpload = async () => {
    setMessage(null);
    try {
      // No permission request is needed to open the photo library.
      const result = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], quality: 0.7 });
      if (result.canceled || !result.assets?.[0]) return;
      const file = await assetToUpload(result.assets[0]);
      await upload.mutateAsync({ target: { follow_up_id: followUpId }, file, description: 'Follow-up evidence' });
      setMessage({ tone: 'success', text: 'Evidence uploaded.' });
    } catch (e) {
      setMessage({ tone: 'danger', text: (e as Error).message || 'Upload failed.' });
    }
  };

  return (
    <View style={styles.detailSection}>
      <Text style={styles.detailLabel}>EVIDENCE FILES</Text>
      {evidence.isLoading ? (
        <ActivityIndicator color={C.teal} />
      ) : evidence.error && !evidence.data ? (
        <View>
          <InlineNotice tone="danger" text={`Could not load evidence: ${(evidence.error as Error).message}`} />
          <Pressable onPress={() => void evidence.refetch()} accessibilityRole="button">
            <Text style={styles.viewButtonText}>Try again</Text>
          </Pressable>
        </View>
      ) : (evidence.data ?? []).length === 0 ? (
        <Text style={styles.responseText}>No files uploaded yet.</Text>
      ) : (
        (evidence.data ?? []).map((e) => (
          <View key={e.id} style={styles.evidenceRow} accessibilityLabel={`Evidence file ${e.original_filename}`}>
            <View style={{ flex: 1 }}>
              <Text style={styles.detailValue} numberOfLines={1}>{e.original_filename}</Text>
              <Text style={styles.detailSecondary}>{formatBytes(e.file_size_bytes)} · {formatDateTime(e.created_at)}</Text>
            </View>
          </View>
        ))
      )}
      {message ? <View style={{ marginTop: 8 }}><InlineNotice tone={message.tone} text={message.text} /></View> : null}
      {canUpload ? (
        <Pressable
          style={[styles.secondaryAction, upload.isPending && styles.disabled]}
          onPress={() => void pickAndUpload()}
          disabled={upload.isPending}
          accessibilityRole="button"
          accessibilityLabel="Upload evidence photo"
          accessibilityState={{ disabled: upload.isPending, busy: upload.isPending }}
        >
          {upload.isPending ? <ActivityIndicator color={C.navy} /> : <Text style={styles.secondaryActionText}>Upload evidence photo</Text>}
        </Pressable>
      ) : null}
    </View>
  );
}
