import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Layout } from './components/Layout'
import { NotFound } from './components/NotFound'
import { FirstRunWizard } from './components/FirstRunWizard'
import { useReposStore, useWikiStore } from './stores'
import {
  OverviewPage,
  ArchitecturePage,
  WorkflowPage,
  DirectoryPage,
  FilePage,
} from './components/pages'

function WelcomePage() {
  return (
    <div className="text-center py-12">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">Welcome to Ọya</h1>
      <p className="text-gray-600 dark:text-gray-400 max-w-md mx-auto">
        Generate comprehensive documentation for your codebase. Click "Generate Wiki" to get
        started.
      </p>
    </div>
  )
}

function App() {
  const repos = useReposStore((s) => s.repos)
  const activeRepo = useReposStore((s) => s.activeRepo)
  const repoStatus = useWikiStore((s) => s.repoStatus)
  const fetchRepos = useReposStore((s) => s.fetchRepos)
  const fetchActiveRepo = useReposStore((s) => s.fetchActiveRepo)

  // Determine if we're in legacy mode (WORKSPACE_PATH set, no multi-repo)
  // or multi-repo mode (repos loaded from registry)
  const isLegacyMode = repoStatus !== null && repos.length === 0

  // Show first-run wizard if:
  // - Not in legacy mode (WORKSPACE_PATH not set)
  // - No repos in the registry
  // - No active repo
  const showFirstRunWizard = !isLegacyMode && repos.length === 0 && activeRepo === null

  const handleFirstRunComplete = async () => {
    // Refresh repos after adding first one
    await fetchRepos()
    await fetchActiveRepo()
  }

  if (showFirstRunWizard) {
    return <FirstRunWizard onComplete={handleFirstRunComplete} />
  }

  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<OverviewPage />} />
          <Route path="/architecture" element={<ArchitecturePage />} />
          <Route path="/workflows/:slug" element={<WorkflowPage />} />
          <Route path="/directories/:slug" element={<DirectoryPage />} />
          <Route path="/files/:slug" element={<FilePage />} />
          <Route path="/welcome" element={<WelcomePage />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  )
}

export default App
