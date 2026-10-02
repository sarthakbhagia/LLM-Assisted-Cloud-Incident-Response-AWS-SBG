import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App.jsx'
import './index.css'

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null, errorInfo: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true }
  }

  componentDidCatch(error, errorInfo) {
    this.setState({ error, errorInfo })
    console.error('Uncaught error:', error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '20px',
          backgroundColor: '#050505',
          color: '#F2F2F2',
          fontFamily: 'Inter, system-ui, sans-serif'
        }}>
          <div style={{
            maxWidth: '500px',
            padding: '32px',
            backgroundColor: '#111113',
            border: '1px solid #2A2A2D',
            borderRadius: '6px',
            textAlign: 'center'
          }}>
            <div style={{
              width: '48px', height: '48px',
              backgroundColor: '#321419',
              border: '1px solid #D63C4B',
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 16px'
            }}>
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#D63C4B" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
                <line x1="12" y1="9" x2="12" y2="13"></line>
                <line x1="12" y1="17" x2="12.01" y2="17"></line>
              </svg>
            </div>
            <h2 style={{ margin: '0 0 8px', fontSize: '18px', fontWeight: '600', color: '#F2F2F2' }}>
              Application Error
            </h2>
            <p style={{ margin: '0 0 16px', fontSize: '13px', color: '#85858C' }}>
              Something went wrong. The error has been logged to the console.
            </p>
            {this.state.error && (
              <details style={{ textAlign: 'left', marginBottom: '16px' }}>
                <summary style={{ cursor: 'pointer', color: '#85858C', fontSize: '12px' }}>Error Details</summary>
                <pre style={{
                  marginTop: '8px',
                  padding: '12px',
                  backgroundColor: '#050505',
                  border: '1px solid #2A2A2D',
                  borderRadius: '4px',
                  fontSize: '11px',
                  fontFamily: 'JetBrains Mono, monospace',
                  color: '#A8C5DA',
                  overflow: 'auto',
                  maxHeight: '200px',
                  textAlign: 'left'
                }}>
                  {this.state.error && this.state.error.toString()}
                  {this.state.errorInfo && '\n\n' + this.state.errorInfo.componentStack}
                </pre>
              </details>
            )}
            <button
              onClick={() => window.location.reload()}
              style={{
                backgroundColor: '#1B1B1F',
                border: '1px solid #2A2A2D',
                color: '#F2F2F2',
                padding: '10px 24px',
                borderRadius: '5px',
                fontSize: '13px',
                fontWeight: '500',
                cursor: 'pointer',
                transition: 'all 75ms'
              }}
              onMouseOver={(e) => e.target.style.borderColor = '#3A3A3E'}
              onMouseOut={(e) => e.target.style.borderColor = '#2A2A2D'}
            >
              Reload Page
            </button>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}

// Global error handlers
window.addEventListener('error', (event) => {
  console.error('Global error:', event.error || event.message)
})

window.addEventListener('unhandledrejection', (event) => {
  console.error('Unhandled rejection:', event.reason)
})

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ErrorBoundary>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </ErrorBoundary>
  </React.StrictMode>,
)