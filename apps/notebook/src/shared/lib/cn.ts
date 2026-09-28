// Class names together: conditions (clsx), and of two Tailwind classes for one property the later
// one wins (tailwind-merge) — as one would expect from the order, which plain CSS does not promise.
import { clsx, type ClassValue } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

// our own tokens tailwind-merge cannot know from Tailwind's defaults (styles.css's @theme)
const twMerge = extendTailwindMerge({ extend: { theme: { animate: ["blink", "rise"] } } });

export const cn = (...classes: ClassValue[]) => twMerge(clsx(classes));
