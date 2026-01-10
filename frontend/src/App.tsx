import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AppProvider } from './context/AppContext';
import { Layout } from './components/Layout';
import {
  OverviewPage,
  ArchitecturePage,
  WorkflowPage,
  DirectoryPage,
  FilePage,
} from './components/pages';

function WelcomePage() {
  return (
    <div className="text-center py-12">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
        Welcome to Ọya
      </h1>
      <p className="text-gray-600 dark:text-gray-400 max-w-md mx-auto">
        Generate comprehensive documentation for your codebase.
        Click "Generate Wiki" to get started.
      </p>
    </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AppProvider>
        <Layout>
          <Routes>
            <Route path="/" element={<OverviewPage />} />
            <Route path="/architecture" element={<ArchitecturePage />} />
            <Route path="/workflows/:slug" element={<WorkflowPage />} />
            <Route path="/directories/:slug" element={<DirectoryPage />} />
            <Route path="/files/:slug" element={<FilePage />} />
            <Route path="/welcome" element={<WelcomePage />} />
          </Routes>
        </Layout>
      </AppProvider>
    </BrowserRouter>
  );
}

export default App;
