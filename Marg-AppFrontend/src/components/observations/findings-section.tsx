import { useState } from 'react';
import { Text, View } from 'react-native';

import { Button, Card, EmptyState, InlineNotice, QueryView, StatusBadge } from '@/components/ui/states';
import { Field, fieldStyles, MutationError, SectionTitle } from '@/components/visits/field-ui';
import { useCreateFinding, useDecideFinding, useFindings } from '@/hooks/api';
import type { ObservationResponse } from '@/lib/api/generated';

export function FindingsSection({ observation }: { observation: ObservationResponse }) {
  const findings = useFindings(observation.id);
  const decide = useDecideFinding();
  const [adding, setAdding] = useState(false);
  const isDraft = observation.status === 'draft';

  const pending = decide.isPending ? decide.variables : undefined;

  return (
    <>
      <SectionTitle
        title="Findings"
        right={!isDraft && !adding ? <Button label="+ Add finding" variant="secondary" onPress={() => setAdding(true)} /> : null}
      />
      {isDraft ? <InlineNotice text="Submit the observation to record findings." /> : null}
      {adding ? <AddFindingForm observationId={observation.id} onDone={() => setAdding(false)} /> : null}
      <MutationError error={decide.error} />
      <QueryView query={findings} loadingLabel="Loading findings…">
        {(list) =>
          list.length === 0 ? (
            <EmptyState title="No findings yet" message={isDraft ? undefined : 'Add a finding or analyse the observation with Classroom Coach.'} />
          ) : (
            list.map((f) => (
              <Card key={f.id}>
                <View style={fieldStyles.rowBetween}>
                  <Text style={fieldStyles.itemTitle}>{f.title}</Text>
                  <StatusBadge status={f.status} label={f.status === 'ai_suggested' ? 'Awaiting approval' : undefined} />
                </View>
                {f.category ? <Text style={fieldStyles.muted}>{f.category}</Text> : null}
                <Text style={fieldStyles.itemText}>{f.description}</Text>
                {f.mentor_comment ? <Text style={fieldStyles.muted}>Comment: {f.mentor_comment}</Text> : null}
                {f.status === 'ai_suggested' ? (
                  <View style={[fieldStyles.row, { marginTop: 10 }]}>
                    <Button
                      label="Approve"
                      onPress={() => decide.mutate({ id: f.id, status: 'mentor_approved' })}
                      loading={pending?.id === f.id && pending.status === 'mentor_approved'}
                      disabled={decide.isPending}
                      style={fieldStyles.grow}
                      accessibilityLabel={`Approve finding: ${f.title}`}
                    />
                    <Button
                      label="Reject"
                      variant="danger"
                      onPress={() => decide.mutate({ id: f.id, status: 'rejected' })}
                      loading={pending?.id === f.id && pending.status === 'rejected'}
                      disabled={decide.isPending}
                      style={fieldStyles.grow}
                      accessibilityLabel={`Reject finding: ${f.title}`}
                    />
                  </View>
                ) : null}
              </Card>
            ))
          )
        }
      </QueryView>
    </>
  );
}

function AddFindingForm({ observationId, onDone }: { observationId: string; onDone: () => void }) {
  const create = useCreateFinding();
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [category, setCategory] = useState('');
  const [error, setError] = useState<string | null>(null);

  const save = () => {
    setError(null);
    if (!title.trim() || !description.trim()) return setError('Enter a title and a description.');
    create.mutate(
      { observation_id: observationId, title: title.trim(), description: description.trim(), category: category.trim() || null },
      { onSuccess: onDone },
    );
  };

  return (
    <Card>
      <Text style={fieldStyles.formTitle}>New finding</Text>
      <Field label="Title" value={title} onChangeText={setTitle} maxLength={200} />
      <Field label="Description" value={description} onChangeText={setDescription} multiline />
      <Field label="Category (optional)" value={category} onChangeText={setCategory} placeholder="e.g. teaching practice" maxLength={100} />
      <Text style={[fieldStyles.muted, { marginBottom: 10 }]}>New findings start as suggestions; approve them to make them official.</Text>
      {error ? <InlineNotice tone="danger" text={error} /> : null}
      <MutationError error={create.error} />
      <View style={fieldStyles.row}>
        <Button label="Cancel" variant="secondary" onPress={onDone} disabled={create.isPending} style={fieldStyles.grow} />
        <Button label="Save finding" onPress={save} loading={create.isPending} style={fieldStyles.grow} />
      </View>
    </Card>
  );
}
