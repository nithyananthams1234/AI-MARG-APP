import { useLocalSearchParams, useRouter } from 'expo-router';

import { ObservationDetail } from '@/components/observations/observation-detail';
import { ObservationList } from '@/components/observations/observation-list';

export default function ObservationsScreen() {
  const router = useRouter();
  const { observationId, visitId } = useLocalSearchParams<{ observationId?: string; visitId?: string }>();

  const back = (fallback: '/dashboard' | '/observations') => () => {
    if (router.canGoBack()) router.back();
    else router.replace(fallback);
  };

  if (observationId) {
    return (
      <ObservationDetail
        observationId={observationId}
        onBack={back('/observations')}
        onDeleted={() => router.replace('/observations')}
        onOpenVisit={(id) => router.push({ pathname: '/visits', params: { visitId: id } })}
      />
    );
  }

  return (
    <ObservationList
      key={visitId ?? 'all'}
      initialVisitId={visitId}
      onBack={back('/dashboard')}
      onOpen={(id) => router.push({ pathname: '/observations', params: { observationId: id } })}
    />
  );
}
