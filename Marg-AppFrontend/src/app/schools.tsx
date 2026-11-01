import { useLocalSearchParams, useRouter } from 'expo-router';

import { SchoolDetail } from '@/components/schools/school-detail';
import { SchoolList } from '@/components/schools/school-list';

export default function SchoolsScreen() {
  const router = useRouter();
  const { schoolId } = useLocalSearchParams<{ schoolId?: string }>();

  const back = (fallback: '/dashboard' | '/schools') => () => {
    if (router.canGoBack()) router.back();
    else router.replace(fallback);
  };

  if (schoolId) {
    return (
      <SchoolDetail
        schoolId={schoolId}
        onBack={back('/schools')}
        onPlanVisit={() => router.push({ pathname: '/visits', params: { schoolId } })}
        onAskCoach={(schoolName) => router.push({ pathname: '/classroom-coach', params: { schoolId, schoolName } })}
        onOpenVisit={(visitId) => router.push({ pathname: '/visits', params: { visitId } })}
        onOpenObservation={(observationId) => router.push({ pathname: '/observations', params: { observationId } })}
      />
    );
  }

  return <SchoolList onBack={back('/dashboard')} onOpen={(s) => router.push({ pathname: '/schools', params: { schoolId: s.id } })} />;
}
