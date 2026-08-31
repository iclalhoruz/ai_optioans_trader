import { clsx, type ClassValue } from "clsx"
import { extendTailwindMerge } from "tailwind-merge"

// tailwind-merge only knows Tailwind's default scale out of the box. Our
// design tokens (font-data-mono-sm, text-headline-md, etc.) are custom names
// it can't infer on its own - without telling it about them, overriding e.g.
// a button's text style via className wouldn't dedupe and both classes would
// ship to the DOM with unpredictable cascade order.
const twMerge = extendTailwindMerge({
  extend: {
    classGroups: {
      "font-size": [
        "text-headline-md",
        "text-label-caps",
        "text-display-lg",
        "text-data-mono-sm",
        "text-body-base",
        "text-data-mono-lg",
      ],
      "font-family": [
        "font-headline-md",
        "font-label-caps",
        "font-display-lg",
        "font-data-mono-sm",
        "font-body-base",
        "font-data-mono-lg",
      ],
    },
  },
})

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
