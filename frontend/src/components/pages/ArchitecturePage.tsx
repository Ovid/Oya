import { useCallback } from 'react';
import { PageLoader } from '../PageLoader';
import { getArchitecture } from '../../api/client';

export function ArchitecturePage() {
  const loadPage = useCallback(() => getArchitecture(), []);
  return <PageLoader loadPage={loadPage} />;
}
