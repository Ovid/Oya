import { useState, useRef, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { askQuestionStream } from '../api/client'
import { CONFIDENCE_COLORS, QA_DEFAULTS, QA_STORAGE_KEY } from '../config'
import { QASettingsPopover, type QASettings } from './QASettingsPopover'
import { formatElapsedTime } from './generationConstants'
import { useWikiStore, useGenerationStore } from '../stores'
import type { Citation, SearchQuality, ConfidenceLevel } from '../types'
import { ThinkingIndicator } from './ThinkingIndicator'

interface QAMessage {
  question: string
  answer: string
  citations: Citation[]
  confidence: ConfidenceLevel
  disclaimer: string
  searchQuality: SearchQuality
  durationSeconds: number
}

interface AskPanelProps {
  isOpen: boolean
  onClose: () => void
}

function loadSettings(): QASettings {
  try {
    const stored = localStorage.getItem(QA_STORAGE_KEY)
    if (stored) {
      const parsed = JSON.parse(stored)
      return {
        quickMode: parsed.quickMode ?? QA_DEFAULTS.quickMode,
        temperature: parsed.temperature ?? QA_DEFAULTS.temperature,
        timeoutMinutes: parsed.timeoutMinutes ?? QA_DEFAULTS.timeoutMinutes,
      }
    }
  } catch {
    // Ignore parse errors, use defaults
  }
  return { ...QA_DEFAULTS }
}

function saveSettings(settings: QASettings): void {
  localStorage.setItem(QA_STORAGE_KEY, JSON.stringify(settings))
}

export function AskPanel({ isOpen, onClose }: AskPanelProps) {
  const currentJob = useGenerationStore((s) => s.currentJob)
  const wikiTree = useWikiStore((s) => s.wikiTree)
  const isGenerating = currentJob?.status === 'running' || currentJob?.status === 'pending'
  const hasWiki =
    wikiTree &&
    (wikiTree.overview ||
      wikiTree.architecture ||
      wikiTree.workflows.length > 0 ||
      wikiTree.directories.length > 0 ||
      wikiTree.files.length > 0)

  const [question, setQuestion] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [messages, setMessages] = useState<QAMessage[]>([])
  const [error, setError] = useState<string | null>(null)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [settings, setSettings] = useState<QASettings>(loadSettings)
  const [currentStatus, setCurrentStatus] = useState<string | null>(null)
  const [pendingQuestion, setPendingQuestion] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const abortControllerRef = useRef<AbortController | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Auto-scroll to bottom when messages or status changes
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, currentStatus])

  // Auto-resize textarea as content changes
  useEffect(() => {
    const textarea = textareaRef.current
    if (!textarea) return

    textarea.style.height = 'auto'
    const maxHeight = 96 // ~4 rows
    const newHeight = Math.min(textarea.scrollHeight, maxHeight)
    textarea.style.height = `${newHeight}px`
    textarea.style.overflowY = textarea.scrollHeight > maxHeight ? 'auto' : 'hidden'
  }, [question])

  // Save settings when they change
  const handleSettingsChange = useCallback((newSettings: QASettings) => {
    setSettings(newSettings)
    saveSettings(newSettings)
  }, [])

  // Clear conversation
  const handleClear = useCallback(() => {
    setMessages([])
    setSessionId(null)
    setError(null)
    setCurrentStatus(null)
    setPendingQuestion(null)
  }, [])

  // Ref to track start time for duration calculation
  const startTimeRef = useRef<number>(0)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!question.trim() || isLoading) return

    const trimmedQuestion = question.trim()
    setPendingQuestion(trimmedQuestion)
    setQuestion('')
    setIsLoading(true)
    setError(null)
    startTimeRef.current = Date.now()
    setCurrentStatus('Searching')

    // Create abort controller with timeout
    const abortController = new AbortController()
    abortControllerRef.current = abortController
    const timeoutMs = settings.timeoutMinutes * 60 * 1000
    const timeoutId = setTimeout(() => {
      abortController.abort()
    }, timeoutMs)

    try {
      await askQuestionStream(
        {
          question: trimmedQuestion,
          session_id: sessionId,
          quick_mode: settings.quickMode,
          temperature: settings.temperature,
        },
        {
          onToken: () => {
            // No longer used - answer comes in done event
          },
          onStatus: (stage, pass) => {
            setCurrentStatus(`${stage}${pass > 1 ? ` (pass ${pass})` : ''}`)
          },
          onDone: (data) => {
            const durationSeconds = Math.floor((Date.now() - startTimeRef.current) / 1000)
            setMessages((prev) => [
              ...prev,
              {
                question: trimmedQuestion,
                answer: data.answer,
                citations: data.citations,
                confidence: data.confidence as ConfidenceLevel,
                disclaimer: data.disclaimer,
                searchQuality: data.search_quality,
                durationSeconds,
              },
            ])
            if (data.session_id) {
              setSessionId(data.session_id)
            }
            setCurrentStatus(null)
            setPendingQuestion(null)
          },
          onError: (message) => {
            setError(message)
            setCurrentStatus(null)
            setPendingQuestion(null)
          },
        },
        abortController.signal
      )
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        setError(`Request timed out after ${settings.timeoutMinutes} minutes`)
      } else {
        setError(err instanceof Error ? err.message : 'Failed to get answer')
      }
      setCurrentStatus(null)
      setPendingQuestion(null)
    } finally {
      clearTimeout(timeoutId)
      abortControllerRef.current = null
      setIsLoading(false)
    }
  }

  const renderCitation = (citation: Citation, index: number) => (
    <Link key={index} to={citation.url} className="text-blue-600 hover:underline text-sm mr-2">
      {citation.title}
    </Link>
  )

  if (!isOpen) return null

  return (
    <div className="w-full bg-white dark:bg-gray-800 flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex justify-between items-center shrink-0">
        <h2 className="font-semibold text-gray-900 dark:text-white">Ask about this codebase</h2>
        <div className="flex items-center gap-1">
          {messages.length > 0 && (
            <button
              onClick={handleClear}
              className="text-sm text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 px-2"
              title="Clear conversation"
            >
              Clear
            </button>
          )}
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
      </div>

      {/* Generation in progress banner */}
      {isGenerating && (
        <div className="p-3 bg-yellow-50 dark:bg-yellow-900/20 text-yellow-800 dark:text-yellow-200 text-sm border-b border-yellow-200 dark:border-yellow-800">
          Q&A is unavailable while the wiki is being generated.
        </div>
      )}

      {/* No wiki banner */}
      {!hasWiki && !isGenerating && (
        <div className="p-3 bg-yellow-50 dark:bg-yellow-900/20 text-yellow-800 dark:text-yellow-200 text-sm border-b border-yellow-200 dark:border-yellow-800">
          Generate a wiki first to enable Q&A.
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto overflow-x-hidden p-4 space-y-4">
        {messages.length === 0 && !currentStatus && !pendingQuestion && (
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
              <div className={`px-3 py-1 rounded text-xs ${CONFIDENCE_COLORS[msg.confidence]}`}>
                {msg.disclaimer}
              </div>

              {/* Answer content */}
              <div className="prose prose-sm dark:prose-invert max-w-none">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.answer}</ReactMarkdown>
              </div>

              {/* Citations */}
              {msg.citations.length > 0 && (
                <div className="pt-2 border-t border-gray-200 dark:border-gray-700">
                  <span className="text-xs text-gray-500 mr-2">Sources:</span>
                  {msg.citations.map(renderCitation)}
                </div>
              )}

              {/* Search quality warning */}
              {(!msg.searchQuality.semantic_searched || !msg.searchQuality.fts_searched) && (
                <div className="text-xs text-yellow-600 dark:text-yellow-400">
                  {!msg.searchQuality.semantic_searched && 'Vector search unavailable. '}
                  {!msg.searchQuality.fts_searched && 'Text search unavailable.'}
                </div>
              )}

              {/* Duration */}
              <div className="text-xs text-gray-400 dark:text-gray-500 italic">
                Thought for {formatElapsedTime(msg.durationSeconds)}
              </div>
            </div>
          </div>
        ))}

        {/* Pending question and status indicator */}
        {(currentStatus || pendingQuestion) && (
          <div className="space-y-2">
            {/* Show current question while waiting */}
            {pendingQuestion && (
              <div className="bg-gray-100 dark:bg-gray-700 rounded-lg p-3">
                <p className="text-sm text-gray-900 dark:text-white">{pendingQuestion}</p>
              </div>
            )}

            {/* Status indicator */}
            {currentStatus && (
              <ThinkingIndicator text={currentStatus === 'thinking' ? 'Thinking' : currentStatus} />
            )}
          </div>
        )}

        {error && (
          <div className="p-3 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 rounded-lg text-sm">
            {error}
          </div>
        )}

        {/* Scroll anchor */}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <form
        onSubmit={handleSubmit}
        className="p-4 border-t border-gray-200 dark:border-gray-700 shrink-0"
      >
        <div className="flex gap-2 items-end">
          <textarea
            ref={textareaRef}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask a question..."
            rows={1}
            className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm resize-none"
            disabled={isLoading || isGenerating || !hasWiki}
          />
          <QASettingsPopover settings={settings} onChange={handleSettingsChange} />
          <button
            type="submit"
            disabled={isLoading || !question.trim() || isGenerating || !hasWiki}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm"
          >
            {isLoading ? '...' : 'Ask'}
          </button>
        </div>
      </form>
    </div>
  )
}
