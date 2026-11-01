import * as ImagePicker from 'expo-image-picker';
import { useState } from 'react';
import { Platform, Text, View } from 'react-native';

import { Button, Card, EmptyState, InlineNotice, QueryView } from '@/components/ui/states';
import { Field, fieldStyles, MutationError, SectionTitle } from '@/components/visits/field-ui';
import { useEvidence, useUploadEvidence } from '@/hooks/api';
import { formatDateTime } from '@/lib/format';
import { assetToUpload, EVIDENCE_TYPES } from '@/lib/upload';

const MAX_BYTES = 10 * 1024 * 1024;

const formatSize = (bytes: number) => (bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`);

export function EvidenceSection({ observationId }: { observationId: string }) {
  const evidence = useEvidence({ observation_id: observationId });
  const upload = useUploadEvidence();
  const [description, setDescription] = useState('');
  const [message, setMessage] = useState<{ tone: 'success' | 'danger'; text: string } | null>(null);

  const pick = async (source: 'library' | 'camera') => {
    setMessage(null);
    upload.reset();
    if (Platform.OS !== 'web') {
      const perm = source === 'camera' ? await ImagePicker.requestCameraPermissionsAsync() : await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (!perm.granted) {
        setMessage({ tone: 'danger', text: `Permission to use the ${source === 'camera' ? 'camera' : 'photo library'} was not granted.` });
        return;
      }
    }
    const options: ImagePicker.ImagePickerOptions = { mediaTypes: ['images'], quality: 0.7 };
    const result = source === 'camera' ? await ImagePicker.launchCameraAsync(options) : await ImagePicker.launchImageLibraryAsync(options);
    if (result.canceled || !result.assets?.length) return;
    const asset = result.assets[0];
    if (asset.mimeType && !EVIDENCE_TYPES.includes(asset.mimeType)) {
      setMessage({ tone: 'danger', text: 'Only JPEG or PNG images can be uploaded.' });
      return;
    }
    if (asset.fileSize && asset.fileSize > MAX_BYTES) {
      setMessage({ tone: 'danger', text: 'The file is larger than 10 MB. Choose a smaller image.' });
      return;
    }
    try {
      const file = await assetToUpload(asset);
      await upload.mutateAsync({ target: { observation_id: observationId }, file, description: description.trim() || undefined });
      setDescription('');
      setMessage({ tone: 'success', text: 'Evidence uploaded.' });
    } catch {
      // Shown via upload.error.
    }
  };

  return (
    <>
      <SectionTitle title="Evidence" />
      <Card>
        <Field
          label="Description (optional)"
          value={description}
          onChangeText={setDescription}
          placeholder="e.g. Blackboard work, student worksheet (no faces)"
          maxLength={1000}
        />
        <View style={fieldStyles.row}>
          <Button label="Upload photo" variant="secondary" onPress={() => void pick('library')} loading={upload.isPending} style={fieldStyles.grow} />
          {Platform.OS !== 'web' ? (
            <Button label="Take photo" variant="secondary" onPress={() => void pick('camera')} disabled={upload.isPending} style={fieldStyles.grow} />
          ) : null}
        </View>
        <Text style={[fieldStyles.muted, { marginTop: 8 }]}>JPEG or PNG, up to 10 MB. Avoid photos where students can be identified.</Text>
        {message ? <View style={{ marginTop: 10 }}><InlineNotice tone={message.tone} text={message.text} /></View> : null}
        <MutationError error={upload.error} />
      </Card>
      <QueryView query={evidence} loadingLabel="Loading evidence…">
        {(list) =>
          list.length === 0 ? (
            <EmptyState title="No evidence yet" message="Upload photos of classroom work to support this observation." />
          ) : (
            <Card>
              {list.map((e) => (
                <View key={e.id} style={{ paddingVertical: 6 }}>
                  <Text style={fieldStyles.itemTitle} numberOfLines={1}>
                    {e.original_filename}
                  </Text>
                  <Text style={fieldStyles.muted}>
                    {e.content_type} · {formatSize(e.file_size_bytes)} · {formatDateTime(e.created_at)}
                  </Text>
                  {e.description ? <Text style={fieldStyles.itemText}>{e.description}</Text> : null}
                </View>
              ))}
            </Card>
          )
        }
      </QueryView>
    </>
  );
}
