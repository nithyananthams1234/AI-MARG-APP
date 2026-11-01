import { useLocalSearchParams, useRouter } from 'expo-router';

import { VisitDetail } from '@/components/visits/visit-detail';
import { VisitList } from '@/components/visits/visit-list';

export default function VisitsScreen() {
  const router = useRouter();
  const { visitId, schoolId } = useLocalSearchParams<{ visitId?: string; schoolId?: string }>();

  const back = (fallback: '/dashboard' | '/visits') => () => {
    if (router.canGoBack()) router.back();
    else router.replace(fallback);
  };

  if (visitId) {
    return (
      <VisitDetail
        visitId={visitId}
        onBack={back('/visits')}
        onRecordObservation={() => router.push({ pathname: '/observations', params: { visitId } })}
        onOpenObservation={(id) => router.push({ pathname: '/observations', params: { observationId: id } })}
        onOpenSchool={(id) => router.push({ pathname: '/schools', params: { schoolId: id } })}
        onOpenCoach={(id, selectedSchoolId, schoolName) =>
          router.push({ pathname: '/classroom-coach', params: { visitId: id, schoolId: selectedSchoolId, schoolName } })
        }
      />
    );
  }

  return (
    <VisitList
      key={schoolId ?? 'all'}
      initialSchoolId={schoolId}
      onBack={back('/dashboard')}
      onOpen={(id) => router.push({ pathname: '/visits', params: { visitId: id } })}
    />
  );
}
