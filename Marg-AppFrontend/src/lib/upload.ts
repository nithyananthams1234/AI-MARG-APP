import { Platform } from 'react-native';

import type { UploadFile } from '@/lib/api/services';

/** Allowed by the backend evidence endpoint. */
export const EVIDENCE_TYPES = ['image/jpeg', 'image/png', 'application/pdf'];

/** Convert an expo-image-picker asset into an evidence upload file (web + native). */
export async function assetToUpload(asset: { uri: string; fileName?: string | null; mimeType?: string | null }): Promise<UploadFile> {
  const type = asset.mimeType && EVIDENCE_TYPES.includes(asset.mimeType) ? asset.mimeType : 'image/jpeg';
  const ext = type === 'image/png' ? 'png' : type === 'application/pdf' ? 'pdf' : 'jpg';
  const name = asset.fileName || `evidence-${Date.now()}.${ext}`;
  if (Platform.OS === 'web') {
    const blob = await (await fetch(asset.uri)).blob();
    return { uri: asset.uri, name, type, blob };
  }
  return { uri: asset.uri, name, type };
}
