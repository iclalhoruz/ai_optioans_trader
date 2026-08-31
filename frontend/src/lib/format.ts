const timestampFormatter = new Intl.DateTimeFormat("en-US", {
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hour12: false,
  timeZone: "UTC",
})

// "2026-05-12 09:41:22 UTC" from an ISO timestamp.
export function formatTimestampUtc(isoTimestamp: string): string {
  const parts = timestampFormatter.formatToParts(new Date(isoTimestamp))
  const get = (type: Intl.DateTimeFormatPartTypes) => parts.find((part) => part.type === type)?.value ?? ""
  return `${get("year")}-${get("month")}-${get("day")} ${get("hour")}:${get("minute")}:${get("second")} UTC`
}

export function formatDuration(seconds: number): string {
  return `${seconds.toFixed(1)}s`
}
