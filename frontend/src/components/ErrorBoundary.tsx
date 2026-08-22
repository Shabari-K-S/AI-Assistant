import { Component, type ErrorInfo, type ReactNode } from 'react'
import { AlertTriangle, RefreshCw } from 'lucide-react'

interface Props {
  children: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
  errorInfo: ErrorInfo | null
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
    errorInfo: null,
  }

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error, errorInfo: null }
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Athena UI ErrorBoundary caught an error:', error, errorInfo)
    this.setState({ error, errorInfo })
  }

  public handleReload = () => {
    window.location.reload()
  }

  public handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null })
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen w-screen bg-[#03070b] text-[#e8fbff] flex flex-col items-center justify-center p-4 font-mono select-none">
          <div className="max-w-md w-full bg-[rgba(6,14,21,0.95)] border border-[rgba(255,93,93,0.5)] shadow-[0_0_30px_rgba(255,93,93,0.3)] rounded-xl p-6 text-center space-y-4">
            <div className="flex justify-center text-[#ff5d5d]">
              <AlertTriangle size={42} className="animate-pulse" />
            </div>
            <h2 className="font-display text-sm font-bold tracking-[0.2em] text-[#ff5d5d]">
              INTERFACE EXCEPTION CAUGHT
            </h2>
            <p className="text-[11px] text-[#7da4b8] leading-relaxed">
              Athena's holographic interface encountered a rendering fault. The system core remains intact.
            </p>
            {this.state.error && (
              <pre className="p-2.5 bg-[rgba(0,0,0,0.6)] border border-[rgba(255,93,93,0.2)] rounded text-[9.5px] text-[#ff7e7e] text-left overflow-x-auto max-h-32">
                {this.state.error.message || String(this.state.error)}
              </pre>
            )}
            <div className="flex items-center justify-center gap-3 pt-2">
              <button
                onClick={this.handleReset}
                className="px-4 py-2 bg-[rgba(65,230,255,0.15)] hover:bg-[rgba(65,230,255,0.25)] border border-[rgba(65,230,255,0.4)] text-[#41e6ff] text-xs font-bold rounded transition-all"
              >
                RECOVER HUD
              </button>
              <button
                onClick={this.handleReload}
                className="px-4 py-2 bg-[#41e6ff] text-[#03070b] hover:bg-[#7ef3ff] text-xs font-bold rounded transition-all flex items-center gap-1.5 shadow-[0_0_12px_rgba(65,230,255,0.4)]"
              >
                <RefreshCw size={12} />
                <span>REBOOT</span>
              </button>
            </div>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}
