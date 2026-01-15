import { useCallback } from 'react'
import { useParams } from 'react-router-dom'
import { PageLoader } from '../PageLoader'
import { getWorkflow } from '../../api/client'

export function WorkflowPage() {
  const { slug } = useParams<{ slug: string }>()
  const loadPage = useCallback(() => getWorkflow(slug!), [slug])
  return <PageLoader loadPage={loadPage} />
}
