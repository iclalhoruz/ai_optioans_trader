import { GlassPanel } from "@/components/ui/GlassPanel"

interface ComingSoonPageProps {
  title: string
  description?: string
}

// Placeholder for a nav destination that has a real route but no screen
// built yet - keeps sidebar links honest (real navigation, not href="#")
// without faking content that doesn't exist. `description` says *why* it's
// empty / what it'll hold once built, so it doesn't read as an arbitrary
// unfinished page - only pass one when there's a concrete plan for it.
export function ComingSoonPage({ title, description }: ComingSoonPageProps) {
  return (
    <GlassPanel className="mx-auto flex max-w-2xl flex-col items-center justify-center gap-2 p-16 text-center">
      <h2 className="font-headline-md text-headline-md text-on-surface">{title}</h2>
      <p className="text-on-surface-variant">{description ?? "This screen hasn't been built yet."}</p>
    </GlassPanel>
  )
}
