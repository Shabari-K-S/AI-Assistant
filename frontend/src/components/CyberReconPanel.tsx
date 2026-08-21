import { memo, useState } from 'react'
import { Shield, ShieldAlert, ShieldCheck, Globe, Lock, Activity, Zap } from 'lucide-react'

interface Props {
  onSend: (text: string) => Promise<boolean> | Promise<void> | void
  disabled?: boolean
}

export const CyberReconPanel = memo(function CyberReconPanel({ onSend, disabled }: Props) {
  const [target, setTarget] = useState('localhost:2026')
  const [loadingAction, setLoadingAction] = useState<string | null>(null)

  const handleTrigger = async (type: string, queryTemplate: string) => {
    if (!target.trim() || disabled) return
    setLoadingAction(type)
    const prompt = queryTemplate.replace('{TARGET}', target.trim())
    await onSend(prompt)
    setTimeout(() => setLoadingAction(null), 1200)
  }

  return (
    <div className="bg-[#0a0d14]/90 border border-cyan-500/20 rounded-xl p-4 backdrop-blur-md shadow-2xl space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-cyan-500/10 pb-3">
        <div className="flex items-center space-x-2">
          <div className="p-2 rounded-lg bg-cyan-500/10 border border-cyan-500/30 text-cyan-400">
            <Shield className="w-5 h-5 animate-pulse" />
          </div>
          <div>
            <h2 className="text-sm font-semibold tracking-wider text-cyan-200 uppercase font-mono">
              Cyber Recon & DAST Matrix
            </h2>
            <p className="text-xs text-gray-400">Autonomous Penetration Testing & Threat Intelligence</p>
          </div>
        </div>
        <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-mono">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
          <span>SCOPED ACTIVE</span>
        </div>
      </div>

      {/* Target Input */}
      <div className="flex items-center space-x-2 bg-[#05070a] border border-cyan-500/20 rounded-lg p-1.5 focus-within:border-cyan-400 transition-colors">
        <div className="pl-2 text-cyan-500 font-mono text-xs">TARGET://</div>
        <input
          type="text"
          value={target}
          onChange={(e) => setTarget(e.target.value)}
          placeholder="e.g. localhost:2026, google.com, 192.168.1.1"
          className="flex-1 bg-transparent text-sm text-cyan-100 placeholder-gray-600 focus:outline-none font-mono px-2"
          disabled={disabled}
        />
        <button
          onClick={() => handleTrigger('quick_all', 'Athena, perform a complete cybersecurity reconnaissance and DAST scan on target {TARGET}.')}
          disabled={disabled || !target.trim()}
          className="px-3 py-1.5 bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-black font-semibold text-xs rounded-md transition-all flex items-center space-x-1 shadow-lg shadow-cyan-500/20"
        >
          <Zap className="w-3.5 h-3.5" />
          <span>FULL AUDIT</span>
        </button>
      </div>

      {/* Action Grid */}
      <div className="grid grid-cols-2 gap-2.5">
        <button
          onClick={() => handleTrigger('dast', 'Athena, run a comprehensive web vulnerability and DAST security scan on {TARGET}.')}
          disabled={disabled || loadingAction === 'dast'}
          className="p-3 bg-red-950/20 hover:bg-red-950/40 border border-red-500/20 hover:border-red-500/40 rounded-lg text-left transition-all group flex flex-col justify-between space-y-2"
        >
          <div className="flex items-center justify-between w-full">
            <ShieldAlert className="w-4 h-4 text-red-400 group-hover:scale-110 transition-transform" />
            <span className="text-[10px] font-mono text-red-400/80 px-1.5 py-0.5 rounded bg-red-500/10">DAST SCAN</span>
          </div>
          <div>
            <div className="text-xs font-semibold text-red-200">Web Vulnerability Scan</div>
            <div className="text-[11px] text-gray-400">SQLi, XSS, Sensitive Files</div>
          </div>
        </button>

        <button
          onClick={() => handleTrigger('ssl', 'Athena, inspect the SSL/TLS certificate validity, expiration, and cipher suites for {TARGET}.')}
          disabled={disabled || loadingAction === 'ssl'}
          className="p-3 bg-cyan-950/20 hover:bg-cyan-950/40 border border-cyan-500/20 hover:border-cyan-500/40 rounded-lg text-left transition-all group flex flex-col justify-between space-y-2"
        >
          <div className="flex items-center justify-between w-full">
            <Lock className="w-4 h-4 text-cyan-400 group-hover:scale-110 transition-transform" />
            <span className="text-[10px] font-mono text-cyan-400/80 px-1.5 py-0.5 rounded bg-cyan-500/10">TLS 1.3</span>
          </div>
          <div>
            <div className="text-xs font-semibold text-cyan-200">SSL Certificate Audit</div>
            <div className="text-[11px] text-gray-400">SANs, Expiry, Cipher Strength</div>
          </div>
        </button>

        <button
          onClick={() => handleTrigger('dns', 'Athena, run DNS reconnaissance and audit SPF/DMARC email security records for {TARGET}.')}
          disabled={disabled || loadingAction === 'dns'}
          className="p-3 bg-purple-950/20 hover:bg-purple-950/40 border border-purple-500/20 hover:border-purple-500/40 rounded-lg text-left transition-all group flex flex-col justify-between space-y-2"
        >
          <div className="flex items-center justify-between w-full">
            <Globe className="w-4 h-4 text-purple-400 group-hover:scale-110 transition-transform" />
            <span className="text-[10px] font-mono text-purple-400/80 px-1.5 py-0.5 rounded bg-purple-500/10">DNS/EMAIL</span>
          </div>
          <div>
            <div className="text-xs font-semibold text-purple-200">DNS & Email Security</div>
            <div className="text-[11px] text-gray-400">MX, SPF, DMARC Spoofing</div>
          </div>
        </button>

        <button
          onClick={() => handleTrigger('net', 'Athena, run network latency and connectivity diagnostics for {TARGET}.')}
          disabled={disabled || loadingAction === 'net'}
          className="p-3 bg-emerald-950/20 hover:bg-emerald-950/40 border border-emerald-500/20 hover:border-emerald-500/40 rounded-lg text-left transition-all group flex flex-col justify-between space-y-2"
        >
          <div className="flex items-center justify-between w-full">
            <Activity className="w-4 h-4 text-emerald-400 group-hover:scale-110 transition-transform" />
            <span className="text-[10px] font-mono text-emerald-400/80 px-1.5 py-0.5 rounded bg-emerald-500/10">TCP PING</span>
          </div>
          <div>
            <div className="text-xs font-semibold text-emerald-200">Network Diagnostic</div>
            <div className="text-[11px] text-gray-400">Latency, Jitter, Reachability</div>
          </div>
        </button>
      </div>

      {/* Threat Advisory Footer */}
      <div className="flex items-center justify-between text-[11px] font-mono text-gray-400 bg-black/40 px-3 py-2 rounded-lg border border-white/5">
        <span className="flex items-center space-x-1.5">
          <ShieldCheck className="w-3.5 h-3.5 text-cyan-400" />
          <span>Strict Allowlist Policy Enforced</span>
        </span>
        <button
          onClick={() => onSend('Athena, what are the latest high-severity CVE security advisories?')}
          className="text-cyan-400 hover:text-cyan-300 underline flex items-center space-x-1"
        >
          <span>CVE Advisories</span>
        </button>
      </div>
    </div>
  )
})
