import { useCallback } from 'react';
import { PageLoader } from '../PageLoader';
import { getOverview } from '../../api/client';

export function OverviewPage() {
  const loadPage = useCallback(() => getOverview(), []);
  return <PageLoader loadPage={loadPage} />;
}
