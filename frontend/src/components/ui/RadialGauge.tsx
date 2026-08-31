interface RadialGaugeProps {
  percent: number
  label: string
}

const RADIUS = 44
const CIRCUMFERENCE = 2 * Math.PI * RADIUS

// Circular gauge with two decorative rotating rings around a real progress
// ring - used for conviction scores and (later) chaos-sandbox stress scores,
// anywhere a single 0-100 value deserves more visual weight than a number.
export function RadialGauge({ percent, label }: RadialGaugeProps) {
  const clamped = Math.min(100, Math.max(0, percent))
  const dashOffset = CIRCUMFERENCE * (1 - clamped / 100)

  return (
    <div className="relative flex h-40 w-40 items-center justify-center">
      <svg
        className="absolute inset-0 h-full w-full -rotate-90 animate-[spin_12s_linear_infinite] opacity-40"
        viewBox="0 0 100 100"
      >
        <circle cx="50" cy="50" r="48" fill="none" stroke="#00d1ff" strokeWidth="1.5" strokeDasharray="2 4" />
      </svg>
      <svg
        className="absolute inset-0 h-full w-full rotate-90 animate-[spin_8s_linear_infinite_reverse] opacity-50"
        viewBox="0 0 100 100"
      >
        <circle cx="50" cy="50" r="38" fill="none" stroke="#a4e6ff" strokeWidth="1" strokeDasharray="4 8" />
      </svg>
      <svg className="relative z-10 h-full w-full -rotate-90" viewBox="0 0 100 100">
        <circle cx="50" cy="50" r={RADIUS} fill="none" stroke="#1a1c20" strokeWidth="6" />
        <circle
          cx="50"
          cy="50"
          r={RADIUS}
          fill="none"
          stroke="#00d1ff"
          strokeWidth="6"
          strokeDasharray={CIRCUMFERENCE}
          strokeDashoffset={dashOffset}
          className="transition-all duration-1000 ease-out"
          style={{ filter: "drop-shadow(0 0 6px rgba(0, 209, 255, 0.8))" }}
        />
      </svg>
      <div className="absolute inset-0 z-20 flex flex-col items-center justify-center">
        <span className="font-data-mono-lg text-3xl font-bold text-primary-container neon-text-cyan">
          {Math.round(clamped)}
          <span className="text-base">%</span>
        </span>
        <span className="mt-1 font-data-mono-sm text-[9px] uppercase tracking-[0.2em] text-primary-container/80">
          {label}
        </span>
      </div>
    </div>
  )
}
