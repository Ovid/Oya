import { useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { PageLoader } from '../PageLoader';
import { getFile } from '../../api/client';

export function FilePage() {
  const { slug } = useParams<{ slug: string }>();
  const loadPage = useCallback(() => getFile(slug!), [slug]);
  return <PageLoader loadPage={loadPage} />;
}
