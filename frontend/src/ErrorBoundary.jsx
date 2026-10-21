import { Component } from 'react'

// A render error used to leave a blank page that looked like a crash. This shows what happened and a Reload button the person presses; the page never reloads by itself (no loop).
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { failed: false }
  }

  static getDerivedStateFromError() {
    return { failed: true }
  }

  render() {
    if (!this.state.failed) return this.props.children
    return (
      <div role="alert" style={{ padding: 24, maxWidth: 480, margin: '10vh auto', font: '16px/1.5 system-ui, sans-serif', color: 'var(--c-text, #1f2a24)', background: 'var(--c-surface, #fffdf8)', border: '1px solid var(--c-line, #ded5c0)', borderRadius: 12 }}>
        <h1 style={{ fontSize: 20, margin: '0 0 8px' }}>Something went wrong</h1>
        <p style={{ margin: '0 0 16px' }}>The page stopped because of an error. Your saved plans and field checks are safe on the server. Reload to continue.</p>
        <button type="button" onClick={() => window.location.reload()} style={{ minHeight: 44, padding: '0 20px', font: 'inherit', fontWeight: 600, borderRadius: 12, border: 0, background: 'var(--c-primary, #1f5d3a)', color: 'var(--c-on-primary, #fff)' }}>
          Reload
        </button>
      </div>
    )
  }
}
