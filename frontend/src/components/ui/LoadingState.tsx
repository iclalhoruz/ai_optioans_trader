interface LoadingStateProps {
  label?: string
}

export function LoadingState({ label = "Loading…" }: LoadingStateProps) {
  return <div className="flex items-center justify-center p-12 text-on-surface-variant">{label}</div>
}
