import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { askQuestion } from '../api/client';
import type { QAResponse, QAMode, Citation } from '../types';

interface QADockProps {
  pageContext?: {
    page_type: string;
    slug: string;
  };
}

export function QADock({ pageContext }: QADockProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [question, setQuestion] = useState('');
  const [mode, setMode] = useState<QAMode>('gated');
  const [isLoading, setIsLoading] = useState(false);
  const [response, setResponse] = useState<QAResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim()) return;

    setIsLoading(true);
    setError(null);

    try {
      const result = await askQuestion({
        question: question.trim(),
        context: pageContext,
        mode,
      });
      setResponse(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to get answer');
    } finally {
      setIsLoading(false);
    }
  };

  const renderCitation = (citation: Citation, index: number) => (
    <span
      key={index}
      className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200 mr-1"
      title={citation.lines ? `Lines: ${citation.lines}` : undefined}
    >
      {citation.title}
    </span>
  );

  return (
    <div className="fixed bottom-0 left-0 right-0 bg-white dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700 shadow-lg z-50">
      {/* Collapsed bar */}
      <div
        className={`flex items-center px-4 py-2 cursor-pointer ${isExpanded ? 'border-b border-gray-200 dark:border-gray-700' : ''}`}
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <svg
          className={`w-5 h-5 mr-2 text-gray-500 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
        </svg>
        <span className="text-gray-600 dark:text-gray-400 text-sm">
          Ask about this codebase...
        </span>
        <div className="ml-auto flex items-center gap-2 text-xs text-gray-500">
          <span className={mode === 'gated' ? 'text-green-600' : 'text-yellow-600'}>
            {mode === 'gated' ? 'Evidence-gated' : 'Loose mode'}
          </span>
        </div>
      </div>

      {/* Expanded content */}
      {isExpanded && (
        <div className="max-h-80 overflow-y-auto">
          {/* Mode toggle and input */}
          <form onSubmit={handleSubmit} className="p-4">
            <div className="flex gap-2 mb-3">
              <button
                type="button"
                onClick={() => setMode('gated')}
                className={`px-3 py-1 text-xs rounded ${
                  mode === 'gated'
                    ? 'bg-green-600 text-white'
                    : 'bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300'
                }`}
              >
                Evidence-gated
              </button>
              <button
                type="button"
                onClick={() => setMode('loose')}
                className={`px-3 py-1 text-xs rounded ${
                  mode === 'loose'
                    ? 'bg-yellow-600 text-white'
                    : 'bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300'
                }`}
              >
                Loose mode
              </button>
            </div>

            <div className="flex gap-2">
              <input
                type="text"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="Ask a question about the codebase..."
                className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                disabled={isLoading}
              />
              <button
                type="submit"
                disabled={isLoading || !question.trim()}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isLoading ? 'Asking...' : 'Ask'}
              </button>
            </div>
          </form>

          {/* Error message */}
          {error && (
            <div className="px-4 pb-4">
              <div className="p-3 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 rounded-lg text-sm">
                {error}
              </div>
            </div>
          )}

          {/* Response */}
          {response && (
            <div className="px-4 pb-4">
              {/* Disclaimer */}
              <div className={`p-2 mb-3 rounded text-xs ${
                response.evidence_sufficient
                  ? 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400'
                  : 'bg-yellow-50 dark:bg-yellow-900/20 text-yellow-700 dark:text-yellow-400'
              }`}>
                {response.disclaimer}
              </div>

              {/* Answer */}
              {response.answer ? (
                <div className="prose prose-sm dark:prose-invert max-w-none">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {response.answer}
                  </ReactMarkdown>
                </div>
              ) : (
                <p className="text-gray-500 dark:text-gray-400 text-sm italic">
                  No answer available. Try rephrasing your question or switching to loose mode.
                </p>
              )}

              {/* Citations */}
              {response.citations.length > 0 && (
                <div className="mt-3 pt-3 border-t border-gray-200 dark:border-gray-700">
                  <span className="text-xs text-gray-500 dark:text-gray-400 mr-2">Sources:</span>
                  {response.citations.map(renderCitation)}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
