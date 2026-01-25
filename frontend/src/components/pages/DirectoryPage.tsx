import { useCallback } from 'react'
import { useParams } from 'react-router-dom'
import { PageLoader } from '../PageLoader'
import { getDirectory } from '../../api/client'
import { wikiSlugToPath } from '../../utils/slug'

export function DirectoryPage() {
  const { slug } = useParams<{ slug: string }>()
  const loadPage = useCallback(() => getDirectory(slug!), [slug])

  // Convert slug back to directory path
  // Handle 'root' specially
  const dirPath = slug === 'root' ? '' : slug ? wikiSlugToPath(slug) : ''

  return <PageLoader loadPage={loadPage} noteScope="directory" noteTarget={dirPath} />
}
