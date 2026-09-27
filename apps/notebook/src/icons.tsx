// Small line icons (24×24, stroke = currentColor).
import type { ReactNode } from "react";

const Icon = ({ children, size = 18 }: { children: ReactNode; size?: number }) => (
  <svg viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor" strokeWidth="1.8"
       strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {children}
  </svg>
);

export const Play = () => <Icon><path d="M8 5.5v13l10.5-6.5z" fill="currentColor" stroke="none" /></Icon>;
export const Pointer = () => <Icon><path d="M6 3.5l12 7.2-5.3 1.2-2.4 5.1z" /></Icon>;
export const WireIcon = () => <Icon><path d="M4 18h6V6h10" /><circle cx="4" cy="18" r="1.6" fill="currentColor" /><circle cx="20" cy="6" r="1.6" fill="currentColor" /></Icon>;
export const Undo = () => <Icon><path d="M9 14L4 9l5-5" /><path d="M4 9h11a5 5 0 010 10h-3" /></Icon>;
export const Redo = () => <Icon><path d="M15 14l5-5-5-5" /><path d="M20 9H9a5 5 0 000 10h3" /></Icon>;
export const Minus = () => <Icon><path d="M6 12h12" /></Icon>;
export const Plus = () => <Icon><path d="M12 6v12M6 12h12" /></Icon>;
export const Up = () => <Icon><path d="M12 19V5M6 11l6-6 6 6" /></Icon>;
export const Down = () => <Icon><path d="M12 5v14M6 13l6 6 6-6" /></Icon>;
export const Trash = () => <Icon><path d="M5 7h14M10 7V5h4v2M7 7l1 12h8l1-12" /></Icon>;
export const CodeIcon = () => <Icon><path d="M9 7l-5 5 5 5M15 7l5 5-5 5" /></Icon>;
export const Rotate = () => <Icon><path d="M20 12a8 8 0 11-2.3-5.7" /><path d="M20 4v5h-5" /></Icon>;
export const Help = () => <Icon><circle cx="12" cy="12" r="9" /><path d="M9.5 9.5a2.5 2.5 0 114 2c-1 .6-1.5 1.1-1.5 2.5" /><circle cx="12" cy="17" r=".6" fill="currentColor" /></Icon>;
export const Bolt = () => <Icon size={22}><path d="M13 2L4 14h7l-1 8 9-12h-7z" fill="currentColor" stroke="none" /></Icon>;
export const Chevron = () => <Icon size={14}><path d="M6 9l6 6 6-6" /></Icon>;
