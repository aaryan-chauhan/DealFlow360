import React from 'react'

export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, errorInfo) {
    console.error('Unhandled React Error:', error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="rounded-2xl border border-rose-200 bg-rose-50 p-6 shadow-sm space-y-3 my-4">
          <h2 className="text-base font-bold text-rose-900">Something went wrong rendering this view.</h2>
          <p className="text-xs text-rose-700 font-mono">
            {this.state.error?.toString() || 'Unknown rendering error'}
          </p>
          <button
            onClick={() => {
              this.setState({ hasError: false, error: null })
              window.location.reload()
            }}
            className="rounded-xl bg-rose-600 px-4 py-2 text-xs font-semibold text-white hover:bg-rose-500 shadow"
          >
            Reload Page
          </button>
        </div>
      )
    }

    return this.props.children
  }
}
