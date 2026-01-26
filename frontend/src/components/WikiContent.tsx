import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import mermaid from 'mermaid'
import type { WikiPage } from '../types'
import { parseFrontmatter } from '../utils/frontmatter'
import { PageInfo } from './PageInfo'

// Initialize mermaid with a readable theme
mermaid.initialize({
  startOnLoad: false,
  theme: 'base',
  themeVariables: {
    // Use high contrast colors
    primaryColor: '#818cf8', // indigo-400
    primaryTextColor: '#1f2937', // gray-800
    primaryBorderColor: '#6366f1', // indigo-500
    lineColor: '#6b7280', // gray-500
    secondaryColor: '#e0e7ff', // indigo-100
    tertiaryColor: '#f3f4f6', // gray-100
    background: '#ffffff',
    mainBkg: '#ffffff',
    secondBkg: '#f9fafb',
    nodeTextColor: '#1f2937',
    textColor: '#1f2937',
  },
  flowchart: {
    htmlLabels: true,
    curve: 'basis',
  },
})

interface MermaidDiagramProps {
  chart: string
}

function MermaidDiagram({ chart }: MermaidDiagramProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [svg, setSvg] = useState<string>('')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const renderChart = async () => {
      if (!containerRef.current) return

      try {
        const id = `mermaid-${Math.random().toString(36).substr(2, 9)}`
        const { svg } = await mermaid.render(id, chart)
        setSvg(svg)
        setError(null)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to render diagram')
        setSvg('')
      }
    }

    renderChart()
  }, [chart])

  if (error) {
    return (
      <div className="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
        <p className="text-sm text-red-600 dark:text-red-400">Failed to render diagram: {error}</p>
        <pre className="mt-2 text-xs text-gray-600 dark:text-gray-400 overflow-auto">{chart}</pre>
      </div>
    )
  }

  return (
    <div
      ref={containerRef}
      className="my-4 p-4 bg-white dark:bg-gray-100 rounded-lg overflow-x-auto border border-gray-200"
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  )
}

interface WikiContentProps {
  page: WikiPage
}

export function WikiContent({ page }: WikiContentProps) {
  const { meta, content } = parseFrontmatter(page.content)

  return (
    <>
      <PageInfo meta={meta} />
      <article className="prose prose-gray dark:prose-invert max-w-none">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
          // Custom heading with id for TOC links
          h1: ({ children }) => {
            const id = String(children)
              .toLowerCase()
              .replace(/[^\w]+/g, '-')
            return <h1 id={id}>{children}</h1>
          },
          h2: ({ children }) => {
            const id = String(children)
              .toLowerCase()
              .replace(/[^\w]+/g, '-')
            return <h2 id={id}>{children}</h2>
          },
          h3: ({ children }) => {
            const id = String(children)
              .toLowerCase()
              .replace(/[^\w]+/g, '-')
            return <h3 id={id}>{children}</h3>
          },
          // Code blocks with syntax highlighting and Mermaid support
          code: ({ className, children, ...props }) => {
            const match = /language-(\w+)/.exec(className || '')
            const language = match ? match[1] : null
            const isInline = !match

            // Handle Mermaid diagrams
            if (language === 'mermaid') {
              return <MermaidDiagram chart={String(children).trim()} />
            }

            if (isInline) {
              return (
                <code
                  className="px-1.5 py-0.5 bg-gray-100 dark:bg-gray-800 rounded text-sm font-mono"
                  {...props}
                >
                  {children}
                </code>
              )
            }

            return (
              <div className="relative group">
                <div className="absolute right-2 top-2 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button
                    onClick={() => navigator.clipboard.writeText(String(children))}
                    className="px-2 py-1 text-xs bg-gray-700 text-gray-300 rounded hover:bg-gray-600"
                  >
                    Copy
                  </button>
                </div>
                <pre className="!bg-gray-900 dark:!bg-gray-950 rounded-lg overflow-x-auto">
                  <code className={`${className} block p-4 text-sm`} {...props}>
                    {children}
                  </code>
                </pre>
              </div>
            )
          },
          // Links open in new tab for external
          a: ({ href, children }) => {
            const isExternal = href?.startsWith('http')
            return (
              <a
                href={href}
                target={isExternal ? '_blank' : undefined}
                rel={isExternal ? 'noopener noreferrer' : undefined}
                className="text-indigo-600 dark:text-indigo-400 hover:underline"
              >
                {children}
              </a>
            )
          },
          // Tables with better styling
          table: ({ children }) => (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                {children}
              </table>
            </div>
          ),
          }}
        >
          {content}
        </ReactMarkdown>
      </article>
    </>
  )
}
