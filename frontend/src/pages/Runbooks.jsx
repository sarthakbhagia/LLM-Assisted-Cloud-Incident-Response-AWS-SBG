import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { BookOpen, ArrowLeft, RefreshCw, AlertTriangle, Code, FileText } from 'lucide-react'
import { apiClient } from '../config/api'
import { FAULT_CLASS_LABELS } from '../utils/constants'

export default function Runbooks() {
  const { fault_class } = useParams()

  if (fault_class) {
    return <RunbookDetail faultClass={fault_class} />
  }
  return <RunbookList />
}

function RunbookList() {
  const navigate = useNavigate()
  const [runbooks, setRunbooks] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchRunbooks = async () => {
    try {
      setLoading(true)
      const data = await apiClient.getRunbooks()
      // Normalize to array — backend may return { runbooks: [] }, { items: [] }, or a raw array
      let list = []
      if (Array.isArray(data)) {
        list = data
      } else if (Array.isArray(data?.runbooks)) {
        list = data.runbooks
      } else if (Array.isArray(data?.items)) {
        list = data.items
      }
      setRunbooks(list)
      setError(null)
    } catch (err) {
      console.error('Failed to fetch runbooks:', err)
      setError('Failed to load runbooks. The backend /api/runbooks endpoint may not be reachable.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchRunbooks()
  }, [])

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-text-primary">Runbooks</h1>
          <p className="text-xs text-text-muted mt-0.5">
            Knowledge base injected into the LLM diagnosis prompt
          </p>
        </div>
        <button onClick={fetchRunbooks} className="btn-ghost" title="Refresh">
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {error ? (
        <div className="card text-center py-12">
          <AlertTriangle className="mx-auto h-10 w-10 text-crimson mb-3" />
          <p className="text-text-secondary mb-4">{error}</p>
          <button onClick={fetchRunbooks} className="btn-primary">
            <RefreshCw className="w-4 h-4 mr-2" />Retry
          </button>
        </div>
      ) : loading ? (
        <RunbookListSkeleton />
      ) : runbooks.length === 0 ? (
        <div className="card text-center py-12">
          <BookOpen className="mx-auto h-12 w-12 text-text-muted mb-4 opacity-50" />
          <h3 className="text-base font-medium text-text-primary mb-1">No runbooks found</h3>
          <p className="text-xs text-text-secondary">
            Runbooks are served from <span className="mono">/knowledge_base/</span> via the Dashboard API Lambda.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {runbooks.map((rb) => {
            const label = FAULT_CLASS_LABELS[rb.fault_class] || rb.fault_class?.replace(/_/g, ' ') || rb.name || '—'
            return (
              <div
                key={rb.fault_class || rb.name}
                onClick={() => navigate(`/runbooks/${rb.fault_class || rb.name}`)}
                className="card hover:bg-bg-elevated transition-colors cursor-pointer flex items-center justify-between group"
              >
                <div className="flex items-center space-x-4">
                  <div className="w-10 h-10 bg-bg-elevated rounded flex items-center justify-center flex-shrink-0">
                    <BookOpen className="w-5 h-5 text-text-muted" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-text-primary">{label}</p>
                    <div className="flex items-center space-x-3 mt-0.5">
                      {rb.file_name && (
                        <span className="mono text-xs text-text-muted">{rb.file_name}</span>
                      )}
                      {rb.char_count != null && (
                        <span className="text-xs text-text-muted">{rb.char_count.toLocaleString()} chars</span>
                      )}
                    </div>
                  </div>
                </div>
                <ArrowLeft className="w-4 h-4 text-text-muted rotate-180 group-hover:text-text-secondary transition-colors" />
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

function RunbookDetail({ faultClass }) {
  const navigate = useNavigate()
  const [content, setContent] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [viewMode, setViewMode] = useState('rendered') // 'rendered' | 'raw'

  const fetchRunbook = async () => {
    try {
      setLoading(true)
      const data = await apiClient.getRunbook(faultClass)
      setContent(data)
      setError(null)
    } catch (err) {
      console.error('Failed to fetch runbook:', err)
      setError('Failed to load runbook')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchRunbook()
  }, [faultClass])

  const label = FAULT_CLASS_LABELS[faultClass] || faultClass?.replace(/_/g, ' ') || faultClass
  const markdownContent = content?.content || content?.markdown || content?.text || (typeof content === 'string' ? content : null)
  const injectedContent = content?.injected_text || markdownContent

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <button onClick={() => navigate('/runbooks')} className="btn-ghost">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Runbooks
          </button>
          <span className="text-text-muted">/</span>
          <span className="text-sm font-medium text-text-primary">{label}</span>
        </div>
        <button onClick={fetchRunbook} className="btn-ghost" title="Refresh">
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {error ? (
        <div className="card text-center py-12">
          <AlertTriangle className="mx-auto h-10 w-10 text-crimson mb-3" />
          <p className="text-text-secondary mb-4">{error}</p>
          <button onClick={fetchRunbook} className="btn-primary">
            <RefreshCw className="w-4 h-4 mr-2" />Retry
          </button>
        </div>
      ) : loading ? (
        <RunbookDetailSkeleton />
      ) : !markdownContent ? (
        <div className="card text-center py-12">
          <BookOpen className="mx-auto h-10 w-10 text-text-muted mb-3 opacity-50" />
          <p className="text-text-secondary">No content available for this runbook</p>
        </div>
      ) : (
        <div className="card">
          {/* View mode toggle */}
          <div className="flex items-center justify-between mb-6 pb-4 border-b border-border-subtle">
            <div className="flex items-center space-x-2">
              <BookOpen className="w-4 h-4 text-text-muted" />
              <span className="text-sm font-medium text-text-primary">{label}</span>
              {content?.file_name && (
                <span className="mono text-xs text-text-muted">({content.file_name})</span>
              )}
            </div>
            <div className="flex items-center bg-bg-elevated rounded p-1 space-x-1">
              <button
                onClick={() => setViewMode('rendered')}
                className={`flex items-center space-x-1.5 px-2.5 py-1 rounded text-xs transition-colors ${
                  viewMode === 'rendered'
                    ? 'bg-bg-surface text-text-primary border border-border-default'
                    : 'text-text-secondary hover:text-text-primary'
                }`}
              >
                <FileText className="w-3.5 h-3.5" />
                <span>Rendered</span>
              </button>
              <button
                onClick={() => setViewMode('raw')}
                className={`flex items-center space-x-1.5 px-2.5 py-1 rounded text-xs transition-colors ${
                  viewMode === 'raw'
                    ? 'bg-bg-surface text-text-primary border border-border-default'
                    : 'text-text-secondary hover:text-text-primary'
                }`}
                title="View as injected into prompt"
              >
                <Code className="w-3.5 h-3.5" />
                <span>As Injected</span>
              </button>
            </div>
          </div>

          {viewMode === 'rendered' ? (
            <div className="prose-runbook max-w-none">
              <SimpleMarkdown content={markdownContent} />
            </div>
          ) : (
            <div className="bg-bg-input rounded-card p-4">
              <pre className="text-xs text-text-code font-mono whitespace-pre-wrap leading-relaxed max-h-[70vh] overflow-y-auto">
                {injectedContent || markdownContent}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// Minimal markdown renderer — headings, bold, lists, code blocks, horizontal rules
function SimpleMarkdown({ content }) {
  const lines = content.split('\n')
  const elements = []
  let i = 0

  while (i < lines.length) {
    const line = lines[i]

    // Code block
    if (line.startsWith('```')) {
      const lang = line.slice(3).trim()
      const codeLines = []
      i++
      while (i < lines.length && !lines[i].startsWith('```')) {
        codeLines.push(lines[i])
        i++
      }
      elements.push(
        <div key={i} className="my-3 bg-bg-input rounded-card overflow-x-auto">
          {lang && <div className="px-3 py-1 text-xs mono text-text-muted border-b border-border-subtle">{lang}</div>}
          <pre className="p-3 text-xs font-mono text-text-code whitespace-pre">{codeLines.join('\n')}</pre>
        </div>
      )
      i++
      continue
    }

    // Headings
    const h3 = line.match(/^### (.+)/)
    const h2 = line.match(/^## (.+)/)
    const h1 = line.match(/^# (.+)/)
    if (h1) {
      elements.push(<h2 key={i} className="text-base font-semibold text-text-primary mt-6 mb-2">{h1[1]}</h2>)
      i++; continue
    }
    if (h2) {
      elements.push(<h3 key={i} className="text-sm font-semibold text-text-primary mt-5 mb-2">{h2[1]}</h3>)
      i++; continue
    }
    if (h3) {
      elements.push(<h4 key={i} className="text-xs font-semibold text-text-secondary uppercase tracking-wide mt-4 mb-1">{h3[1]}</h4>)
      i++; continue
    }

    // HR
    if (/^---+$/.test(line.trim())) {
      elements.push(<hr key={i} className="border-border-subtle my-4" />)
      i++; continue
    }

    // Bullet list item
    if (/^[-*] /.test(line)) {
      const listItems = []
      while (i < lines.length && /^[-*] /.test(lines[i])) {
        listItems.push(lines[i].replace(/^[-*] /, ''))
        i++
      }
      elements.push(
        <ul key={`ul-${i}`} className="my-2 space-y-1 pl-4">
          {listItems.map((item, j) => (
            <li key={j} className="text-xs text-text-secondary list-disc">
              <InlineMarkdown text={item} />
            </li>
          ))}
        </ul>
      )
      continue
    }

    // Numbered list
    if (/^\d+\. /.test(line)) {
      const listItems = []
      while (i < lines.length && /^\d+\. /.test(lines[i])) {
        listItems.push(lines[i].replace(/^\d+\. /, ''))
        i++
      }
      elements.push(
        <ol key={`ol-${i}`} className="my-2 space-y-1 pl-4">
          {listItems.map((item, j) => (
            <li key={j} className="text-xs text-text-secondary list-decimal">
              <InlineMarkdown text={item} />
            </li>
          ))}
        </ol>
      )
      continue
    }

    // Empty line
    if (line.trim() === '') {
      elements.push(<div key={i} className="h-2" />)
      i++; continue
    }

    // Paragraph
    elements.push(
      <p key={i} className="text-xs text-text-secondary leading-relaxed my-1">
        <InlineMarkdown text={line} />
      </p>
    )
    i++
  }

  return <div className="space-y-0">{elements}</div>
}

function InlineMarkdown({ text }) {
  // Handle bold **text**, inline code `code`
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g)
  return (
    <>
      {parts.map((part, i) => {
        if (part.startsWith('**') && part.endsWith('**')) {
          return <strong key={i} className="text-text-primary font-medium">{part.slice(2, -2)}</strong>
        }
        if (part.startsWith('`') && part.endsWith('`')) {
          return <code key={i} className="mono bg-bg-elevated px-1 py-0.5 rounded text-text-code">{part.slice(1, -1)}</code>
        }
        return <span key={i}>{part}</span>
      })}
    </>
  )
}

function RunbookListSkeleton() {
  return (
    <div className="space-y-3">
      {Array.from({ length: 3 }).map((_, i) => (
        <div key={i} className="card flex items-center space-x-4">
          <div className="pulse-loading w-10 h-10 rounded"></div>
          <div className="flex-1">
            <div className="pulse-loading h-4 w-40 mb-2"></div>
            <div className="pulse-loading h-3 w-24"></div>
          </div>
        </div>
      ))}
    </div>
  )
}

function RunbookDetailSkeleton() {
  return (
    <div className="card">
      <div className="flex items-center justify-between mb-6 pb-4 border-b border-border-subtle">
        <div className="pulse-loading h-5 w-40"></div>
        <div className="pulse-loading h-7 w-40 rounded"></div>
      </div>
      <div className="space-y-3">
        <div className="pulse-loading h-6 w-64"></div>
        <div className="pulse-loading h-3 w-full"></div>
        <div className="pulse-loading h-3 w-5/6"></div>
        <div className="pulse-loading h-3 w-full"></div>
        <div className="pulse-loading h-3 w-4/6"></div>
        <div className="pulse-loading h-20 w-full rounded mt-4"></div>
        <div className="pulse-loading h-3 w-full"></div>
        <div className="pulse-loading h-3 w-3/4"></div>
      </div>
    </div>
  )
}
