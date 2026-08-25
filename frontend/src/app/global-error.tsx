'use client'

// Root-level boundary (must render its own <html>). Branded counterpart to
// Next's default global-error so even worst-case crashes carry a readable
// message and a digest instead of an anonymous dead end.
import { useEffect } from 'react'

export default function GlobalError({
  error,
  reset
}: {
  error: Error & { digest?: string };
  reset: () => void
}) {
  useEffect(() => {
    console.error('[agentaudit] global error:', error)
  }, [error])

  return (
    <html lang='en'>
      <body
        style={{
          margin: 0,
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: '#09090b',
          color: '#fafafa',
          fontFamily: 'system-ui, sans-serif'
        }}
      >
        <div style={{ maxWidth: 420, padding: 24, textAlign: 'center' }}>
          <h1 style={{ fontSize: 18, fontWeight: 600, margin: '0 0 12px' }}>
            AgentAudit hit an unexpected error
          </h1>
          <p style={{ fontSize: 14, lineHeight: 1.6, color: '#a1a1aa', margin: '0 0 8px' }}>
            {error.message || 'Something went wrong while rendering the app.'}
          </p>
          {error.digest ? (
            <p style={{ fontSize: 12, fontFamily: 'monospace', color: '#71717a', margin: '0 0 20px' }}>
              digest: {error.digest}
            </p>
          ) : null}
          <button
            type='button'
            onClick={reset}
            style={{
              padding: '8px 16px',
              borderRadius: 8,
              border: '1px solid #27272a',
              background: '#18181b',
              color: '#fafafa',
              fontSize: 13,
              cursor: 'pointer'
            }}
          >
            Reload AgentAudit
          </button>
        </div>
      </body>
    </html>
  )
}
