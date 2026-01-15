import { useState } from 'react'
import { Link } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { askQuestion } from '../api/client'
import { CONFIDENCE_COLORS } from '../config'
import type { QAResponse, Citation } from '../types'

interface QAMessage {
  question: string
  response: QAResponse
}

interface AskPanelProps {
  isOpen: boolean
  onClose: () => void
}

export function AskPanel({ isOpen, onClose }: AskPanelProps) {
  const [question, setQuestion] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [messages, setMessages] = useState<QAMessage[]>([])
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!question.trim() || isLoading) return

    setIsLoading(true)
    setError(null)

    try {
      const response = await askQuestion({ question: question.trim() })
      setMessages((prev) => [...prev, { question: question.trim(), response }])
      setQuestion('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to get answer')
    } finally {
      setIsLoading(false)
    }
  }

  const renderCitation = (citation: Citation, index: number) => (
    <Link
      key={index}
      to={citation.url}
      onClick={onClose}
      className="text-blue-600 hover:underline text-sm mr-2"
    >
      {citation.title}
    </Link>
  )

  if (!isOpen) return null

  return (
    <div className="w-[350px] border-l border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 flex flex-col h-full">
      {/* Header */}
      <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex justify-between items-center">
        <h2 className="font-semibold text-gray-900 dark:text-white">Ask about this codebase</h2>
        <button
          onClick={onClose}
          className="text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="text-center text-gray-500 dark:text-gray-400 text-sm py-8">
            <p>Ask any question about the codebase.</p>
            <p className="mt-2 text-xs">Answers are based on the generated documentation.</p>
          </div>
        )}

        {messages.map((msg, idx) => (
          <div key={idx} className="space-y-2">
            {/* Question */}
            <div className="bg-gray-100 dark:bg-gray-700 rounded-lg p-3">
              <p className="text-sm text-gray-900 dark:text-white">{msg.question}</p>
            </div>

            {/* Answer */}
            <div className="space-y-2">
              {/* Confidence banner */}
              <div
                className={`px-3 py-1 rounded text-xs ${CONFIDENCE_COLORS[msg.response.confidence]}`}
              >
                {msg.response.disclaimer}
              </div>

              {/* Answer content */}
              <div className="prose prose-sm dark:prose-invert max-w-none">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.response.answer}</ReactMarkdown>
              </div>

              {/* Citations */}
              {msg.response.citations.length > 0 && (
                <div className="pt-2 border-t border-gray-200 dark:border-gray-700">
                  <span className="text-xs text-gray-500 mr-2">Sources:</span>
                  {msg.response.citations.map(renderCitation)}
                </div>
              )}

              {/* Search quality warning */}
              {(!msg.response.search_quality.semantic_searched ||
                !msg.response.search_quality.fts_searched) && (
                <div className="text-xs text-yellow-600 dark:text-yellow-400">
                  {!msg.response.search_quality.semantic_searched && 'Vector search unavailable. '}
                  {!msg.response.search_quality.fts_searched && 'Text search unavailable.'}
                </div>
              )}
            </div>
          </div>
        ))}

        {error && (
          <div className="p-3 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 rounded-lg text-sm">
            {error}
          </div>
        )}
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="p-4 border-t border-gray-200 dark:border-gray-700">
        <div className="flex gap-2">
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask a question..."
            className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
            disabled={isLoading}
          />
          <button
            type="submit"
            disabled={isLoading || !question.trim()}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm"
          >
            {isLoading ? '...' : 'Ask'}
          </button>
        </div>
      </form>
    </div>
  )
}
