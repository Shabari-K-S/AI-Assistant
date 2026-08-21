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
    <div className="w-full max-w-4xl mx-auto bg-gradient-to-b from-[#0b1322]/95 to-[#060a12]/95 border border-[rgba(65,230,255,0.22)] rounded-2xl p-3.5 sm:p-5 backdrop-blur-xl shadow-[0_8px_32px_rgba(0,0,0,0.6)] space-y-3.5 sm:space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[rgba(65,230,255,0.12)] pb-3">
        <div className="flex items-center space-x-2.5">
          <div className="p-2 rounded-xl bg-[rgba(65,230,255,0.12)] border border-[rgba(65,230,255,0.35)] text-[#41e6ff] shadow-[0_0_12px_rgba(65,230,255,0.25)]">
            <Shield className="w-4 h-4 sm:w-5 sm:h-5 animate-pulse" />
          </div>
          <div>
            <h2 className="text-xs sm:text-sm font-bold tracking-wider text-[#e8fbff] uppercase font-mono">
              Cyber Recon & DAST Matrix
            </h2>
            <p className="text-[10.5px] sm:text-xs text-[#7da4b8]">Autonomous Penetration Testing & Threat Intelligence</p>
          </div>
        </div>
        <div className="flex items-center space-x-1.5 px-2 sm:px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-[10px] sm:text-xs font-mono font-bold">
          <span className="w-1.5 h-1.5 sm:w-2 sm:h-2 rounded-full bg-emerald-400 animate-ping" />
          <span>SCOPED</span>
        </div>
      </div>

      {/* Target Input */}
      <div className="flex items-center space-x-1.5 sm:space-x-2 bg-[#040811] border border-[rgba(65,230,255,0.25)] rounded-xl p-1.5 focus-within:border-[#41e6ff] focus-within:shadow-[0_0_12px_rgba(65,230,255,0.2)] transition-all">
        <div className="pl-2 text-[#41e6ff] font-mono text-[11px] sm:text-xs font-bold tracking-wider">TARGET://</div>
        <input
          type="text"
          value={target}
          onChange={(e) => setTarget(e.target.value)}
          placeholder="e.g. localhost:2026, google.com"
          className="flex-1 min-w-0 bg-transparent text-xs sm:text-sm text-[#e8fbff] placeholder-gray-500 focus:outline-none font-mono px-1 sm:px-2"
          disabled={disabled}
        />
        <button
          onClick={() => handleTrigger('quick_all', 'Athena, perform a complete cybersecurity reconnaissance and DAST scan on target {TARGET}.')}
          disabled={disabled || !target.trim()}
          className="px-2.5 sm:px-3.5 py-1.5 bg-gradient-to-r from-[#41e6ff] to-[#0088ff] hover:from-[#7beeff] hover:to-[#2299ff] text-[#040811] font-bold text-[11px] sm:text-xs rounded-lg transition-all flex items-center space-x-1 shadow-[0_0_14px_rgba(65,230,255,0.4)] active:scale-95 shrink-0"
        >
          <Zap className="w-3.5 h-3.5" />
          <span>FULL AUDIT</span>
        </button>
      </div>

      {/* Action Grid */}
      <div className="grid grid-cols-2 gap-2 sm:gap-3">
        <button
          onClick={() => handleTrigger('dast', 'Athena, run a comprehensive web vulnerability and DAST security scan on {TARGET}.')}
          disabled={disabled || loadingAction === 'dast'}
          className="p-2.5 sm:p-3.5 bg-gradient-to-br from-red-950/25 to-red-950/10 hover:from-red-950/40 hover:to-red-950/20 border border-red-500/25 hover:border-red-500/50 rounded-xl text-left transition-all group flex flex-col justify-between space-y-1.5 sm:space-y-2 active:scale-98 shadow-sm hover:shadow-[0_0_15px_rgba(239,68,68,0.15)]"
        >
          <div className="flex items-center justify-between w-full">
            <ShieldAlert className="w-4 h-4 text-red-400 group-hover:scale-110 transition-transform" />
            <span className="text-[9px] sm:text-[10px] font-mono text-red-400 font-bold px-1.5 py-0.5 rounded bg-red-500/15">DAST</span>
          </div>
          <div>
            <div className="text-[11.5px] sm:text-xs font-bold text-red-200">Web Vulnerability</div>
            <div className="text-[10px] sm:text-[11px] text-gray-400">SQLi, XSS, Sensitive Files</div>
          </div>
        </button>

        <button
          onClick={() => handleTrigger('ssl', 'Athena, inspect the SSL/TLS certificate validity, expiration, and cipher suites for {TARGET}.')}
          disabled={disabled || loadingAction === 'ssl'}
          className="p-2.5 sm:p-3.5 bg-gradient-to-br from-cyan-950/25 to-cyan-950/10 hover:from-cyan-950/40 hover:to-cyan-950/20 border border-cyan-500/25 hover:border-cyan-500/50 rounded-xl text-left transition-all group flex flex-col justify-between space-y-1.5 sm:space-y-2 active:scale-98 shadow-sm hover:shadow-[0_0_15px_rgba(65,230,255,0.15)]"
        >
          <div className="flex items-center justify-between w-full">
            <Lock className="w-4 h-4 text-cyan-400 group-hover:scale-110 transition-transform" />
            <span className="text-[9px] sm:text-[10px] font-mono text-cyan-400 font-bold px-1.5 py-0.5 rounded bg-cyan-500/15">TLS 1.3</span>
          </div>
          <div>
            <div className="text-[11.5px] sm:text-xs font-bold text-cyan-200">SSL Certificate</div>
            <div className="text-[10px] sm:text-[11px] text-gray-400">SANs, Expiry, Ciphers</div>
          </div>
        </button>

        <button
          onClick={() => handleTrigger('dns', 'Athena, run DNS reconnaissance and audit SPF/DMARC email security records for {TARGET}.')}
          disabled={disabled || loadingAction === 'dns'}
          className="p-2.5 sm:p-3.5 bg-gradient-to-br from-purple-950/25 to-purple-950/10 hover:from-purple-950/40 hover:to-purple-950/20 border border-purple-500/25 hover:border-purple-500/50 rounded-xl text-left transition-all group flex flex-col justify-between space-y-1.5 sm:space-y-2 active:scale-98 shadow-sm hover:shadow-[0_0_15px_rgba(168,85,247,0.15)]"
        >
          <div className="flex items-center justify-between w-full">
            <Globe className="w-4 h-4 text-purple-400 group-hover:scale-110 transition-transform" />
            <span className="text-[9px] sm:text-[10px] font-mono text-purple-400 font-bold px-1.5 py-0.5 rounded bg-purple-500/15">DNS</span>
          </div>
          <div>
            <div className="text-[11.5px] sm:text-xs font-bold text-purple-200">DNS & Email Security</div>
            <div className="text-[10px] sm:text-[11px] text-gray-400">MX, SPF, DMARC Spoofing</div>
          </div>
        </button>

        <button
          onClick={() => handleTrigger('net', 'Athena, run network latency and connectivity diagnostics for {TARGET}.')}
          disabled={disabled || loadingAction === 'net'}
          className="p-2.5 sm:p-3.5 bg-gradient-to-br from-emerald-950/25 to-emerald-950/10 hover:from-emerald-950/40 hover:to-emerald-950/20 border border-emerald-500/25 hover:border-emerald-500/50 rounded-xl text-left transition-all group flex flex-col justify-between space-y-1.5 sm:space-y-2 active:scale-98 shadow-sm hover:shadow-[0_0_15px_rgba(52,211,153,0.15)]"
        >
          <div className="flex items-center justify-between w-full">
            <Activity className="w-4 h-4 text-emerald-400 group-hover:scale-110 transition-transform" />
            <span className="text-[9px] sm:text-[10px] font-mono text-emerald-400 font-bold px-1.5 py-0.5 rounded bg-emerald-500/15">TCP</span>
          </div>
          <div>
            <div className="text-[11.5px] sm:text-xs font-bold text-emerald-200">Network Diagnostic</div>
            <div className="text-[10px] sm:text-[11px] text-gray-400">Latency, Jitter, Reachability</div>
          </div>
        </button>
      </div>

      {/* Threat Advisory Footer */}
      <div className="flex items-center justify-between text-[10px] sm:text-[11px] font-mono text-[#7da4b8] bg-[#040811]/70 px-3 py-2 rounded-xl border border-[rgba(65,230,255,0.1)]">
        <span className="flex items-center space-x-1.5">
          <ShieldCheck className="w-3.5 h-3.5 text-[#41e6ff]" />
          <span>Allowlist Policy Active</span>
        </span>
        <button
          onClick={() => onSend('Athena, what are the latest high-severity CVE security advisories?')}
          className="text-[#41e6ff] hover:text-[#7beeff] font-bold underline flex items-center space-x-1"
        >
          <span>CVE Advisories</span>
        </button>
      </div>
    </div>
  )
})
