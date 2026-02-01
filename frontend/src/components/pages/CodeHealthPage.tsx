import { useCallback } from 'react'
import { PageLoader } from '../PageLoader'
import { getCodeHealth } from '../../api/client'

export function CodeHealthPage() {
  const loadPage = useCallback(() => getCodeHealth(), [])
  return <PageLoader loadPage={loadPage} />
}
