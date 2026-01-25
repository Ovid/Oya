import { useCallback } from 'react'
import { useParams } from 'react-router-dom'
import { PageLoader } from '../PageLoader'
import { getFile } from '../../api/client'
import { wikiSlugToPath } from '../../utils/slug'

export function FilePage() {
  const { slug } = useParams<{ slug: string }>()
  const loadPage = useCallback(() => getFile(slug!), [slug])

  // Convert slug back to file path for note lookup
  const filePath = slug ? wikiSlugToPath(slug) : ''

  return <PageLoader loadPage={loadPage} noteScope="file" noteTarget={filePath} />
}
