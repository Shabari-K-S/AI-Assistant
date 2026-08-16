/**
 * Procedural Web Audio sci-fi sound effects engine for S.A.R.A. HUD.
 * Synthesizes pure Web Audio oscillator waveforms without needing external mp3/wav files.
 */

class SoundEffectsEngine {
  private ctx: AudioContext | null = null
  private enabled: boolean = true

  constructor() {
    // AudioContext will be initialized on first user interaction to comply with browser autoplay policies
  }

  private getContext(): AudioContext | null {
    if (!this.ctx && typeof window !== 'undefined') {
      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext
      if (AudioCtx) {
        this.ctx = new AudioCtx()
      }
    }
    if (this.ctx && this.ctx.state === 'suspended') {
      this.ctx.resume().catch(() => {})
    }
    return this.ctx
  }

  public setEnabled(enabled: boolean) {
    this.enabled = enabled
  }

  public isEnabled(): boolean {
    return this.enabled
  }

  /** Subtle sci-fi click when pressing buttons or chips */
  public click() {
    if (!this.enabled) return
    const ctx = this.getContext()
    if (!ctx) return

    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    const t = ctx.currentTime

    osc.type = 'sine'
    osc.frequency.setValueAtTime(1400, t)
    osc.frequency.exponentialRampToValueAtTime(400, t + 0.04)

    gain.gain.setValueAtTime(0.06, t)
    gain.gain.exponentialRampToValueAtTime(0.001, t + 0.04)

    osc.connect(gain)
    gain.connect(ctx.destination)

    osc.start(t)
    osc.stop(t + 0.04)
  }

  /** Terminal uplink transmission sound */
  public uplink() {
    if (!this.enabled) return
    const ctx = this.getContext()
    if (!ctx) return

    const t = ctx.currentTime
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()

    osc.type = 'triangle'
    osc.frequency.setValueAtTime(580, t)
    osc.frequency.setValueAtTime(880, t + 0.05)
    osc.frequency.setValueAtTime(1240, t + 0.1)

    gain.gain.setValueAtTime(0.08, t)
    gain.gain.exponentialRampToValueAtTime(0.001, t + 0.22)

    osc.connect(gain)
    gain.connect(ctx.destination)

    osc.start(t)
    osc.stop(t + 0.22)
  }

  /** Wake word / Activation futuristic sweep */
  public wakeDetected() {
    if (!this.enabled) return
    const ctx = this.getContext()
    if (!ctx) return

    const t = ctx.currentTime
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()

    osc.type = 'sine'
    osc.frequency.setValueAtTime(440, t)
    osc.frequency.exponentialRampToValueAtTime(1760, t + 0.18)

    gain.gain.setValueAtTime(0.1, t)
    gain.gain.exponentialRampToValueAtTime(0.001, t + 0.25)

    osc.connect(gain)
    gain.connect(ctx.destination)

    osc.start(t)
    osc.stop(t + 0.25)
  }

  /** Response received chime */
  public responseReady() {
    if (!this.enabled) return
    const ctx = this.getContext()
    if (!ctx) return

    const t = ctx.currentTime
    const osc1 = ctx.createOscillator()
    const osc2 = ctx.createOscillator()
    const gain = ctx.createGain()

    osc1.type = 'sine'
    osc1.frequency.setValueAtTime(1046.5, t) // C6
    osc2.type = 'triangle'
    osc2.frequency.setValueAtTime(1318.5, t + 0.06) // E6

    gain.gain.setValueAtTime(0.07, t)
    gain.gain.exponentialRampToValueAtTime(0.001, t + 0.3)

    osc1.connect(gain)
    osc2.connect(gain)
    gain.connect(ctx.destination)

    osc1.start(t)
    osc1.stop(t + 0.3)
    osc2.start(t + 0.06)
    osc2.stop(t + 0.3)
  }

  /** Warning or error sound */
  public error() {
    if (!this.enabled) return
    const ctx = this.getContext()
    if (!ctx) return

    const t = ctx.currentTime
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()

    osc.type = 'sawtooth'
    osc.frequency.setValueAtTime(220, t)
    osc.frequency.setValueAtTime(180, t + 0.08)

    gain.gain.setValueAtTime(0.08, t)
    gain.gain.exponentialRampToValueAtTime(0.001, t + 0.2)

    osc.connect(gain)
    gain.connect(ctx.destination)

    osc.start(t)
    osc.stop(t + 0.2)
  }
}

export const soundFx = new SoundEffectsEngine()
