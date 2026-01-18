import { useState, useRef, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { askQuestionStream } from '../api/client'
import { CONFIDENCE_COLORS, QA_DEFAULTS, QA_STORAGE_KEY } from '../config'
import { QASettingsPopover, type QASettings } from './QASettingsPopover'
import type { Citation, SearchQuality, ConfidenceLevel } from '../types'

interface QAMessage {
  question: string
  answer: string
  citations: Citation[]
  confidence: ConfidenceLevel
  disclaimer: string
  searchQuality: SearchQuality
  isStreaming?: boolean
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
  const [question, setQuestion] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [messages, setMessages] = useState<QAMessage[]>([])
  const [error, setError] = useState<string | null>(null)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [settings, setSettings] = useState<QASettings>(loadSettings)
  const [currentStreamText, setCurrentStreamText] = useState('')
  const [currentStatus, setCurrentStatus] = useState<string | null>(null)
  const [pendingQuestion, setPendingQuestion] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const abortControllerRef = useRef<AbortController | null>(null)

  // Auto-scroll to bottom when messages or streaming text changes
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, currentStreamText])

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
    setCurrentStreamText('')
    setCurrentStatus(null)
    setPendingQuestion(null)
  }, [])

  // Ref to track accumulated stream text (needed because onDone callback captures stale state)
  const streamTextRef = useRef('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!question.trim() || isLoading) return

    const trimmedQuestion = question.trim()
    setPendingQuestion(trimmedQuestion)
    setQuestion('')
    setIsLoading(true)
    setError(null)
    setCurrentStreamText('')
    streamTextRef.current = ''
    setCurrentStatus('Searching...')

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
          onToken: (text) => {
            streamTextRef.current += text
            setCurrentStreamText(streamTextRef.current)
            setCurrentStatus(null)
          },
          onStatus: (stage, pass) => {
            setCurrentStatus(`${stage}${pass > 1 ? ` (pass ${pass})` : ''}`)
          },
          onDone: (data) => {
            const finalAnswer = streamTextRef.current
            setMessages((prev) => [
              ...prev,
              {
                question: trimmedQuestion,
                answer: finalAnswer,
                citations: data.citations,
                confidence: data.confidence as ConfidenceLevel,
                disclaimer: data.disclaimer,
                searchQuality: data.search_quality,
              },
            ])
            if (data.session_id) {
              setSessionId(data.session_id)
            }
            setCurrentStreamText('')
            streamTextRef.current = ''
            setCurrentStatus(null)
            setPendingQuestion(null)
          },
          onError: (message) => {
            setError(message)
            setCurrentStreamText('')
            streamTextRef.current = ''
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
      setCurrentStreamText('')
      streamTextRef.current = ''
      setCurrentStatus(null)
      setPendingQuestion(null)
    } finally {
      clearTimeout(timeoutId)
      abortControllerRef.current = null
      setIsLoading(false)
    }
  }

  const renderCitation = (citation: Citation, index: number) => (
    <Link
      key={index}
      to={citation.url}
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

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && !currentStreamText && !currentStatus && (
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
                className={`px-3 py-1 rounded text-xs ${CONFIDENCE_COLORS[msg.confidence]}`}
              >
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
              {(!msg.searchQuality.semantic_searched ||
                !msg.searchQuality.fts_searched) && (
                <div className="text-xs text-yellow-600 dark:text-yellow-400">
                  {!msg.searchQuality.semantic_searched && 'Vector search unavailable. '}
                  {!msg.searchQuality.fts_searched && 'Text search unavailable.'}
                </div>
              )}
            </div>
          </div>
        ))}

        {/* Streaming response */}
        {(currentStreamText || currentStatus || pendingQuestion) && (
          <div className="space-y-2">
            {/* Show current question while streaming */}
            {pendingQuestion && (
              <div className="bg-gray-100 dark:bg-gray-700 rounded-lg p-3">
                <p className="text-sm text-gray-900 dark:text-white">
                  {pendingQuestion}
                </p>
              </div>
            )}

            {/* Status indicator */}
            {currentStatus && (
              <div className="text-xs text-gray-500 dark:text-gray-400 italic">
                {currentStatus}
              </div>
            )}

            {/* Streaming answer content */}
            {currentStreamText && (
              <div className="prose prose-sm dark:prose-invert max-w-none">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {currentStreamText}
                </ReactMarkdown>
                <span className="inline-block w-2 h-4 bg-blue-500 animate-pulse ml-1" />
              </div>
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
      <form onSubmit={handleSubmit} className="p-4 border-t border-gray-200 dark:border-gray-700">
        <div className="flex gap-2 items-center">
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask a question..."
            className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
            disabled={isLoading}
          />
          <QASettingsPopover settings={settings} onChange={handleSettingsChange} />
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
