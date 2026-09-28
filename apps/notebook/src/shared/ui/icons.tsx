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
export const Hand = () => <Icon><path d="M8 13V6.5a1.5 1.5 0 013 0V11m0-5.5v-1a1.5 1.5 0 013 0V11m0-4.5a1.5 1.5 0 013 0V13c0 4-2.5 7-6.5 7-3 0-4.5-1.5-6-4l-1.8-3a1.5 1.5 0 012.5-1.6L8 13" /></Icon>;
export const Grid = () => <Icon><rect x="4" y="4" width="6.5" height="6.5" rx="1.5" /><rect x="13.5" y="4" width="6.5" height="6.5" rx="1.5" /><rect x="4" y="13.5" width="6.5" height="6.5" rx="1.5" /><rect x="13.5" y="13.5" width="6.5" height="6.5" rx="1.5" /></Icon>;
export const Expand = () => <Icon><path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5" /></Icon>;
export const Shrink = () => <Icon><path d="M9 4v5H4M15 4v5h5M9 20v-5H4M15 20v-5h5" /></Icon>;
export const Search = () => <Icon size={16}><circle cx="11" cy="11" r="6" /><path d="M16 16l4 4" /></Icon>;
export const SchematicIcon = () => <Icon><path d="M3 12h4l1.5-3 3 6 3-6 1.5 3h5" /></Icon>;
export const WarningIcon = () => <Icon><path d="M12 4L2.5 20h19z" /><path d="M12 10v4.5" /><circle cx="12" cy="17.3" r=".7" fill="currentColor" /></Icon>;
export const Pencil = () => <Icon size={16}><path d="M4 20h4L19 9l-4-4L4 16z" /><path d="M13.5 6.5l4 4" /></Icon>;
export const Eye = () => <Icon size={16}><path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z" /><circle cx="12" cy="12" r="2.8" /></Icon>;
export const Target = () => <Icon><circle cx="12" cy="12" r="7" /><circle cx="12" cy="12" r="2" fill="currentColor" /><path d="M12 2v3M12 19v3M2 12h3M19 12h3" /></Icon>;
export const RunAll = () => <Icon><path d="M4 6v12l8-6zM12 6v12l8-6z" fill="currentColor" stroke="none" /></Icon>;
export const Export = () => <Icon><path d="M12 4v11M7.5 10.5L12 15l4.5-4.5" /><path d="M5 17v3h14v-3" /></Icon>;
export const More = () => <Icon>{[6, 12, 18].map((x) => <circle key={x} cx={x} cy="12" r="1.6" fill="currentColor" stroke="none" />)}</Icon>;
export const Cloud = () => <Icon><path d="M7 18.5h10.5a4 4 0 00.6-7.95A6 6 0 006.4 9.2 4.7 4.7 0 007 18.5z" /></Icon>;
export const CloudOff = () => <Icon><path d="M7 18.5h10.5a4 4 0 00.6-7.95A6 6 0 006.4 9.2 4.7 4.7 0 007 18.5z" /><path d="M4 4l16 16" /></Icon>;
export const Notes = () => <Icon><rect x="4" y="4" width="16" height="16" rx="2.5" /><path d="M9.5 4v16" /></Icon>;
export const Upload = () => <Icon><path d="M12 15V4M7.5 8.5L12 4l4.5 4.5" /><path d="M5 15v5h14v-5" /></Icon>;
export const Back = () => <Icon><path d="M14.5 5.5L8 12l6.5 6.5" /></Icon>;
export const OutlineIcon = () => <Icon><path d="M4 6.5h16M8 12h12M8 17.5h12" /></Icon>;
export const Flash = () => <Icon size={16}><path d="M13 2L4 14h7l-1 8 9-12h-7z" fill="currentColor" stroke="none" /></Icon>;
export const Chevron = () => <Icon size={14}><path d="M6 9l6 6 6-6" /></Icon>;
export const Close = () => <Icon><path d="M6 6l12 12M18 6L6 18" /></Icon>;
export const Check = () => <Icon size={16}><path d="M5 12.5l4.5 4.5L19 7.5" /></Icon>;
export const Sun = () => <Icon><circle cx="12" cy="12" r="4" /><path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4" /></Icon>;
export const Moon = () => <Icon><path d="M20 14.5A8 8 0 019.5 4a8 8 0 1010.5 10.5z" /></Icon>;
export const System = () => <Icon><rect x="3" y="4.5" width="18" height="12" rx="2" /><path d="M9 20h6M12 16.5V20" /></Icon>;
export const SignOut = () => <Icon><path d="M14 4.5h3.5a2 2 0 012 2v11a2 2 0 01-2 2H14" /><path d="M10 8l-4 4 4 4M6 12h9.5" /></Icon>;

// the providers' own marks (their colours), for the sign-in buttons
export const GoogleLogo = () => (
  <svg viewBox="0 0 48 48" width="18" height="18" aria-hidden="true">
    <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z" />
    <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z" />
    <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z" />
    <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z" />
  </svg>
);
export const GitHubLogo = () => (
  <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden="true">
    <path d="M12 .5C5.65.5.5 5.65.5 12c0 5.08 3.29 9.39 7.86 10.91.58.11.79-.25.79-.56v-1.96c-3.2.7-3.87-1.54-3.87-1.54-.52-1.33-1.28-1.69-1.28-1.69-1.04-.71.08-.7.08-.7 1.15.08 1.76 1.18 1.76 1.18 1.03 1.76 2.69 1.25 3.35.96.1-.74.4-1.25.73-1.54-2.55-.29-5.24-1.28-5.24-5.68 0-1.26.45-2.28 1.18-3.09-.12-.29-.51-1.46.11-3.04 0 0 .97-.31 3.17 1.18a11 11 0 015.77 0c2.2-1.49 3.17-1.18 3.17-1.18.62 1.58.23 2.75.11 3.04.74.81 1.18 1.83 1.18 3.09 0 4.41-2.69 5.39-5.25 5.67.41.36.78 1.06.78 2.14v3.17c0 .31.21.68.8.56A11.5 11.5 0 0023.5 12C23.5 5.65 18.35.5 12 .5z" />
  </svg>
);
export const MicrosoftLogo = () => (
  <svg viewBox="0 0 23 23" width="18" height="18" aria-hidden="true">
    <path fill="#f25022" d="M1 1h10v10H1z" /><path fill="#7fba00" d="M12 1h10v10H12z" />
    <path fill="#00a4ef" d="M1 12h10v10H1z" /><path fill="#ffb900" d="M12 12h10v10H12z" />
  </svg>
);
export const FolderIcon = () => <Icon size={16}><path d="M3.5 7.5a2 2 0 012-2h3.8l2 2.2h7.2a2 2 0 012 2V17a2 2 0 01-2 2h-13a2 2 0 01-2-2z" /></Icon>;
export const PageIcon = () => <Icon size={16}><path d="M6.5 3.5h7l4 4v13h-11z" /><path d="M13.5 3.5v4h4M9.5 12.5h5M9.5 16h5" /></Icon>;
