import { memo, useState } from 'react'
import { Shield, ShieldAlert, ShieldCheck, Globe, Lock, Activity, Zap, Terminal, Binary, KeyRound, BookOpenCheck, FileText } from 'lucide-react'

interface Props {
  onSend: (text: string) => Promise<boolean> | Promise<void> | void
  disabled?: boolean
}

export const CyberReconPanel = memo(function CyberReconPanel({ onSend, disabled }: Props) {
  const [activeTab, setActiveTab] = useState<'recon' | 'lab'>('recon')
  const [target, setTarget] = useState('localhost:2026')
  const [labInput, setLabInput] = useState('')
  const [labMachine, setLabMachine] = useState('HTB-Target')
  const [loadingAction, setLoadingAction] = useState<string | null>(null)

  const handleTrigger = async (type: string, queryTemplate: string) => {
    if (disabled) return
    setLoadingAction(type)
    const prompt = queryTemplate.replace('{TARGET}', target.trim())
    await onSend(prompt)
    setTimeout(() => setLoadingAction(null), 1200)
  }

  const handleLabTrigger = async (type: string, prompt: string) => {
    if (disabled) return
    setLoadingAction(type)
    await onSend(prompt)
    setTimeout(() => setLoadingAction(null), 1200)
  }

  return (
    <div className="w-full max-w-4xl mx-auto bg-gradient-to-b from-[#0b1322]/95 to-[#060a12]/95 border border-[rgba(65,230,255,0.22)] rounded-2xl p-3.5 sm:p-5 backdrop-blur-xl shadow-[0_8px_32px_rgba(0,0,0,0.6)] space-y-3.5 sm:space-y-4">
      {/* Header with Sub-Tabs */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-[rgba(65,230,255,0.12)] pb-3 gap-2.5">
        <div className="flex items-center space-x-2.5">
          <div className="p-2 rounded-xl bg-[rgba(65,230,255,0.12)] border border-[rgba(65,230,255,0.35)] text-[#41e6ff] shadow-[0_0_12px_rgba(65,230,255,0.25)]">
            <Shield className="w-4 h-4 sm:w-5 sm:h-5 animate-pulse" />
          </div>
          <div>
            <h2 className="text-xs sm:text-sm font-bold tracking-wider text-[#e8fbff] uppercase font-mono">
              Cyber Matrix & Lab Co-Pilot
            </h2>
            <p className="text-[10.5px] sm:text-xs text-[#7da4b8]">Penetration Testing, DAST & CTF Toolkit</p>
          </div>
        </div>

        {/* Mode Selector Tabs */}
        <div className="flex items-center gap-1.5 bg-[#040811] p-1 rounded-xl border border-[rgba(65,230,255,0.2)]">
          <button
            onClick={() => setActiveTab('recon')}
            className={`px-3 py-1 text-[10.5px] font-mono font-bold rounded-lg transition-all ${
              activeTab === 'recon'
                ? 'bg-[#41e6ff] text-[#040811] shadow-[0_0_10px_rgba(65,230,255,0.5)]'
                : 'text-[#7da4b8] hover:text-[#e8fbff]'
            }`}
          >
            RECON & DAST
          </button>
          <button
            onClick={() => setActiveTab('lab')}
            className={`px-3 py-1 text-[10.5px] font-mono font-bold rounded-lg transition-all ${
              activeTab === 'lab'
                ? 'bg-[#ba68ff] text-[#040811] shadow-[0_0_10px_rgba(186,104,255,0.5)]'
                : 'text-[#7da4b8] hover:text-[#e8fbff]'
            }`}
          >
            CTF LAB CO-PILOT
          </button>
        </div>
      </div>

      {activeTab === 'recon' ? (
        <>
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
        </>
      ) : (
        /* CTF & Lab Co-Pilot Mode */
        <div className="space-y-3">
          {/* Quick Payload Decoder & Hash Identifier Sandbox */}
          <div className="p-3 rounded-xl bg-[#040811] border border-[rgba(186,104,255,0.3)] space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-mono font-bold text-[#ba68ff] flex items-center gap-1.5">
                <Binary size={14} /> PAYLOAD DECODER & HASH IDENTIFIER
              </span>
              <span className="text-[9.5px] font-mono text-gray-400">Base64 / Hex / JWT / Hashes</span>
            </div>
            <div className="flex items-center gap-1.5">
              <input
                type="text"
                value={labInput}
                onChange={(e) => setLabInput(e.target.value)}
                placeholder="Paste Base64, Hex, JWT, or Hash (e.g. $2a$..., e3b0c44...)"
                className="flex-1 bg-[#080d18] border border-[rgba(186,104,255,0.25)] rounded-lg px-2.5 py-1.5 text-xs font-mono text-[#e8fbff] placeholder-gray-600 focus:outline-none focus:border-[#ba68ff]"
              />
              <button
                onClick={() => {
                  if (!labInput.trim()) return
                  handleLabTrigger('decode', `Athena, decode and inspect this payload or identify this hash: ${labInput.trim()}`)
                }}
                disabled={disabled || !labInput.trim()}
                className="px-3 py-1.5 bg-[#ba68ff] hover:bg-[#d094ff] text-[#040811] font-bold text-xs rounded-lg font-mono transition-all active:scale-95 shrink-0 shadow-[0_0_12px_rgba(186,104,255,0.4)]"
              >
                ANALYZE
              </button>
            </div>
          </div>

          {/* Active Lab Session Controls */}
          <div className="flex items-center gap-1.5 bg-[#040811] p-1.5 rounded-xl border border-[rgba(99,102,241,0.25)]">
            <div className="pl-1.5 text-indigo-400 font-mono text-[10px] font-bold">MACHINE://</div>
            <input
              type="text"
              value={labMachine}
              onChange={(e) => setLabMachine(e.target.value)}
              placeholder="e.g. HTB-Sau, THM-RootMe"
              className="flex-1 bg-transparent text-xs text-[#e8fbff] placeholder-gray-600 focus:outline-none font-mono px-1.5"
            />
            <button
              onClick={() => handleLabTrigger('session_start', `Athena, start a new lab session for machine ${labMachine || 'Target'} with IP ${target}.`)}
              disabled={disabled || !labMachine.trim()}
              className="px-2.5 py-1 bg-indigo-600 hover:bg-indigo-500 text-white font-mono font-bold text-[10.5px] rounded-lg transition-all active:scale-95 shrink-0"
            >
              TRACK TARGET
            </button>
          </div>

          {/* Active Lab Action Grid */}
          <div className="grid grid-cols-2 gap-2 sm:gap-2.5">
            <button
              onClick={() => handleLabTrigger('session_log', `Athena, log a finding for active lab machine ${labMachine}: completed initial port scan and service enumeration.`)}
              disabled={disabled}
              className="p-2.5 bg-gradient-to-br from-indigo-950/30 to-indigo-950/10 hover:from-indigo-950/50 border border-indigo-500/30 rounded-xl text-left transition-all group space-y-1"
            >
              <div className="flex items-center justify-between">
                <Terminal size={14} className="text-indigo-400" />
                <span className="text-[9px] font-mono text-indigo-400 px-1 py-0.5 rounded bg-indigo-500/15">LOG</span>
              </div>
              <div className="text-xs font-bold text-indigo-200">Log Finding</div>
              <div className="text-[10px] text-gray-400">Record milestone to timeline</div>
            </button>

            <button
              onClick={() => handleLabTrigger('session_export', `Athena, export the active lab session walkthrough report to the notes vault.`)}
              disabled={disabled}
              className="p-2.5 bg-gradient-to-br from-purple-950/30 to-purple-950/10 hover:from-purple-950/50 border border-purple-500/30 rounded-xl text-left transition-all group space-y-1"
            >
              <div className="flex items-center justify-between">
                <FileText size={14} className="text-purple-400" />
                <span className="text-[9px] font-mono text-purple-400 px-1 py-0.5 rounded bg-purple-500/15">REPORT</span>
              </div>
              <div className="text-xs font-bold text-purple-200">Export Walkthrough</div>
              <div className="text-[10px] text-gray-400">Generate Markdown dossier in Vault</div>
            </button>

            <button
              onClick={() => handleLabTrigger('cve_mentor', `Athena, explain the vulnerability mechanics and defensive remediations for Log4Shell CVE-2021-44228.`)}
              disabled={disabled}
              className="p-2.5 bg-gradient-to-br from-cyan-950/30 to-cyan-950/10 hover:from-cyan-950/50 border border-cyan-500/30 rounded-xl text-left transition-all group space-y-1"
            >
              <div className="flex items-center justify-between">
                <BookOpenCheck size={14} className="text-cyan-400" />
                <span className="text-[9px] font-mono text-cyan-400 px-1 py-0.5 rounded bg-cyan-500/15">MENTOR</span>
              </div>
              <div className="text-xs font-bold text-cyan-200">Vulnerability Mentor</div>
              <div className="text-[10px] text-gray-400">Root cause & mechanics guide</div>
            </button>

            <button
              onClick={() => handleLabTrigger('searchsploit', `Athena, search Exploit-DB and CVE advisories for Apache 2.4.49.`)}
              disabled={disabled}
              className="p-2.5 bg-gradient-to-br from-emerald-950/30 to-emerald-950/10 hover:from-emerald-950/50 border border-emerald-500/30 rounded-xl text-left transition-all group space-y-1"
            >
              <div className="flex items-center justify-between">
                <KeyRound size={14} className="text-emerald-400" />
                <span className="text-[9px] font-mono text-emerald-400 px-1 py-0.5 rounded bg-emerald-500/15">SEARCHSPLOIT</span>
              </div>
              <div className="text-xs font-bold text-emerald-200">CVE & Exploit-DB</div>
              <div className="text-[10px] text-gray-400">Advisories & mitigations</div>
            </button>

            <button
              onClick={() => handleLabTrigger('vpn_status', `Athena, check the active lab VPN tunnel interface and IP status.`)}
              disabled={disabled}
              className="p-2.5 bg-gradient-to-br from-blue-950/30 to-blue-950/10 hover:from-blue-950/50 border border-blue-500/30 rounded-xl text-left transition-all group space-y-1"
            >
              <div className="flex items-center justify-between">
                <Globe size={14} className="text-blue-400" />
                <span className="text-[9px] font-mono text-blue-400 px-1 py-0.5 rounded bg-blue-500/15">VPN TUNNEL</span>
              </div>
              <div className="text-xs font-bold text-blue-200">Lab VPN Telemetry</div>
              <div className="text-[10px] text-gray-400">Inspect tun0 & assigned IP</div>
            </button>

            <button
              onClick={() => handleLabTrigger('env_check', `Athena, audit installed security tools and SecLists wordlists in the Termux environment.`)}
              disabled={disabled}
              className="p-2.5 bg-gradient-to-br from-amber-950/30 to-amber-950/10 hover:from-amber-950/50 border border-amber-500/30 rounded-xl text-left transition-all group space-y-1"
            >
              <div className="flex items-center justify-between">
                <Activity size={14} className="text-amber-400" />
                <span className="text-[9px] font-mono text-amber-400 px-1 py-0.5 rounded bg-amber-500/15">TOOLCHAIN</span>
              </div>
              <div className="text-xs font-bold text-amber-200">Termux Toolchain</div>
              <div className="text-[10px] text-gray-400">Audit Nmap, Gobuster, Wordlists</div>
            </button>
          </div>
        </div>
      )}

      {/* Threat Advisory Footer */}
      <div className="flex items-center justify-between text-[10px] sm:text-[11px] font-mono text-[#7da4b8] bg-[#040811]/70 px-3 py-2 rounded-xl border border-[rgba(65,230,255,0.1)]">
        <span className="flex items-center space-x-1.5">
          <ShieldCheck className="w-3.5 h-3.5 text-[#41e6ff]" />
          <span>Strict Allowlist & Lab Safety Enforced</span>
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
