import { memo } from 'react'

const SEGMENTS = 48

interface Props {
  score: number
  threshold: number
  noiseFloor: number
}

/**
 * Live wake-word meter: a segmented "spectrum" bar filled to the current
 * score, with a threshold tick. Fills past the tick flash bright cyan.
 */
export const WakeMeter = memo(function WakeMeter({ score, threshold, noiseFloor }: Props) {
  const hit = score >= threshold
  const fill = Math.min(1, Math.max(0, score))

  return (
    <div className="w-full">
      <div className={`relative h-11 overflow-hidden rounded border transition-all duration-300 ${
        hit 
          ? 'border-[#41e6ff] shadow-[0_0_18px_rgba(65,230,255,0.4)] bg-[rgba(6,22,34,0.85)]' 
          : 'border-[rgba(65,230,255,0.18)] bg-[rgba(6,14,21,0.7)]'
      }`}>
        <div className="relative h-full flex items-end gap-[2px] px-2 pt-1 pb-1">
          {Array.from({ length: SEGMENTS }, (_, i) => {
            const segFill = (i + 0.5) / SEGMENTS
            const on = segFill <= fill
            const hot = on && hit
            return (
              <span
                key={i}
                className="flex-1 transition-[height] duration-75 ease-linear rounded-t-sm"
                style={{
                  height: `${20 + 72 * Math.abs(Math.sin((i / SEGMENTS) * Math.PI * 2))}%`,
                  background: hot
                    ? 'linear-gradient(180deg, #ffffff, #41e6ff)'
                    : on
                      ? 'linear-gradient(180deg, rgba(126,243,255,0.9), rgba(65,230,255,0.5))'
                      : 'rgba(65,230,255,0.07)',
                  boxShadow: hot ? '0 0 12px rgba(65,230,255,0.9)' : 'none',
                }}
              />
            )
          })}

          {/* threshold tick - scoped inside the padded track */}
          <div
            className="absolute inset-y-0 w-0.5 bg-[#ffc24b] shadow-[0_0_8px_rgba(255,194,75,1)] z-10 transition-all duration-100"
            style={{ left: `calc(8px + (100% - 16px) * ${Math.min(1, Math.max(0, threshold))})` }}
            title={`Threshold: ${threshold.toFixed(2)}`}
          >
            <span className="absolute -top-1 -left-1 size-2 rounded-full bg-[#ffc24b]" />
          </div>
        </div>
      </div>

      <div className="mt-1.5 flex items-center justify-between font-mono text-[10px] tracking-widest px-0.5">
        <span className={hit ? 'text-[#eaffff] font-bold' : 'text-[#7da4b8]'}>
          WAKE <span className="hud-num">{score.toFixed(3)}</span>
        </span>
        <span className="text-[#ffc24b]">
          TRIGGER THR {threshold.toFixed(2)}
        </span>
        <span className="text-[#3e5c6d]">
          NOISE {noiseFloor.toFixed(4)}
        </span>
      </div>
    </div>
  )
})
