import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { WikiPage } from '../types';

interface WikiContentProps {
  page: WikiPage;
}

export function WikiContent({ page }: WikiContentProps) {
  return (
    <article className="prose prose-gray dark:prose-invert max-w-none">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          // Custom heading with id for TOC links
          h1: ({ children }) => {
            const id = String(children).toLowerCase().replace(/[^\w]+/g, '-');
            return <h1 id={id}>{children}</h1>;
          },
          h2: ({ children }) => {
            const id = String(children).toLowerCase().replace(/[^\w]+/g, '-');
            return <h2 id={id}>{children}</h2>;
          },
          h3: ({ children }) => {
            const id = String(children).toLowerCase().replace(/[^\w]+/g, '-');
            return <h3 id={id}>{children}</h3>;
          },
          // Code blocks with syntax highlighting placeholder
          code: ({ className, children, ...props }) => {
            const match = /language-(\w+)/.exec(className || '');
            const isInline = !match;

            if (isInline) {
              return (
                <code
                  className="px-1.5 py-0.5 bg-gray-100 dark:bg-gray-800 rounded text-sm font-mono"
                  {...props}
                >
                  {children}
                </code>
              );
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
            );
          },
          // Links open in new tab for external
          a: ({ href, children }) => {
            const isExternal = href?.startsWith('http');
            return (
              <a
                href={href}
                target={isExternal ? '_blank' : undefined}
                rel={isExternal ? 'noopener noreferrer' : undefined}
                className="text-indigo-600 dark:text-indigo-400 hover:underline"
              >
                {children}
              </a>
            );
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
        {page.content}
      </ReactMarkdown>
    </article>
  );
}
