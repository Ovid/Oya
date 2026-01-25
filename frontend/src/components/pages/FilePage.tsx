import { useCallback } from 'react'
import { useParams } from 'react-router-dom'
import { PageLoader } from '../PageLoader'
import { getFile } from '../../api/client'

export function FilePage() {
  const { slug } = useParams<{ slug: string }>()
  const loadPage = useCallback(() => getFile(slug!), [slug])

  // Convert slug back to file path for note lookup
  // Slugs use -- for path separators, so src--main.py -> src/main.py
  const filePath = slug?.replace(/--/g, '/').replace(/\.md$/, '') || ''

  return (
    <PageLoader
      loadPage={loadPage}
      noteScope="file"
      noteTarget={filePath}
    />
  )
}
