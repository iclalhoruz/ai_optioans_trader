interface ErrorStateProps {
  message?: string
}

export function ErrorState({ message = "Something went wrong." }: ErrorStateProps) {
  return <div className="flex items-center justify-center p-12 text-error">{message}</div>
}
