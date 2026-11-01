/**
 * Optional: share a Coach answer the mentor chose with a teacher via
 * WhatsApp. Opens a wa.me link only after explicit mentor approval.
 * Never calls the backend; the app cannot confirm delivery.
 */
import * as Linking from 'expo-linking';
import { useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import { pageStyles } from '@/components/reports/page-chrome';
import { Button, Card, InlineNotice } from '@/components/ui/states';
import { MargColors as C } from '@/constants/theme';
import { notify } from '@/lib/dialogs';

/** Mount with a `key` per chosen answer so the draft and approval reset. */
export function WhatsAppShare({ initialText, onClose }: { initialText: string; onClose: () => void }) {
  const [draft, setDraft] = useState(initialText);
  const [phone, setPhone] = useState('');
  const [approved, setApproved] = useState(false);
  const [opened, setOpened] = useState(false);

  const digits = phone.replace(/\D/g, '');
  const phoneValid = digits.length >= 8 && digits.length <= 15;
  const canOpen = approved && phoneValid && draft.trim().length > 0;

  const open = async () => {
    if (!canOpen) return;
    try {
      await Linking.openURL(`https://wa.me/${digits}?text=${encodeURIComponent(draft.trim())}`);
      setOpened(true);
    } catch {
      notify('WhatsApp unavailable', 'Could not open WhatsApp. Check the phone number and try again.');
    }
  };

  return (
    <Card style={styles.card}>
      <View style={pageStyles.rowBetween}>
        <Text style={[pageStyles.itemTitle, { flex: 1 }]}>Share with a teacher (WhatsApp)</Text>
        <Button label="Close" variant="ghost" onPress={onClose} accessibilityLabel="Close WhatsApp draft" />
      </View>
      <Text style={pageStyles.muted}>
        The draft is based on the Coach answer you chose. Edit it in your own words before sharing. Nothing is sent by this app: WhatsApp opens with
        the text for you to send.
      </Text>

      <Text style={pageStyles.label}>Teacher phone number (with country code)</Text>
      <TextInput
        value={phone}
        onChangeText={(v) => {
          setPhone(v);
          setOpened(false);
        }}
        placeholder="e.g. +91 98765 43210"
        placeholderTextColor={C.muted}
        keyboardType="phone-pad"
        style={pageStyles.input}
        accessibilityLabel="Teacher phone number with country code"
      />
      {phone.length > 0 && !phoneValid ? <Text style={pageStyles.error}>Enter 8 to 15 digits including the country code.</Text> : null}

      <Text style={pageStyles.label}>Message</Text>
      <TextInput
        value={draft}
        onChangeText={(v) => {
          setDraft(v);
          setApproved(false);
        }}
        multiline
        maxLength={3000}
        style={[pageStyles.input, styles.message]}
        accessibilityLabel="Message to the teacher"
      />

      <Pressable
        onPress={() => setApproved((a) => !a)}
        accessibilityRole="checkbox"
        accessibilityState={{ checked: approved }}
        style={styles.approval}
      >
        <View style={[styles.checkbox, approved && styles.checkboxChecked]}>{approved ? <Text style={styles.check}>✓</Text> : null}</View>
        <Text style={styles.approvalText}>I reviewed and approve this message for the teacher.</Text>
      </Pressable>

      <Button label="Continue in WhatsApp" onPress={() => void open()} disabled={!canOpen} accessibilityLabel="Open this message in WhatsApp" />
      {opened ? <InlineNotice tone="info" text="WhatsApp opened. Review and send the message there. This app cannot confirm delivery." /> : null}
    </Card>
  );
}

const styles = StyleSheet.create({
  card: { borderColor: '#BFE7E3', marginTop: 12 },
  message: { minHeight: 140, textAlignVertical: 'top' },
  approval: { flexDirection: 'row', alignItems: 'center', gap: 10, marginVertical: 12 },
  checkbox: { width: 22, height: 22, borderRadius: 6, borderWidth: 2, borderColor: C.muted, alignItems: 'center', justifyContent: 'center' },
  checkboxChecked: { backgroundColor: C.teal, borderColor: C.teal },
  check: { color: '#FFF', fontWeight: '800', fontSize: 13 },
  approvalText: { color: C.text, fontSize: 14, flex: 1 },
});
