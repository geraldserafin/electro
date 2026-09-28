// A menu behind an island's ⋯: it opens under the button; a click outside, Esc or a choice closes
// it. Groups of choices, one of each on (like the theme: system / light / dark).
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { useClickOutside } from "@/shared/hooks/useClickOutside";
import { cn } from "@/shared/lib/cn";
import { Check, More } from "./icons";
import { IslandButton } from "./Island";

const Close = createContext<() => void>(() => {});

export function MenuIsland({ label, children }: { label: string; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const close = useCallback(() => setOpen(false), []);
  useClickOutside(ref, open, close);
  useEffect(() => {
    if (!open) return;
    const esc = (e: KeyboardEvent) => e.key === "Escape" && close();
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [open, close]);
  return (
    <div className="relative" ref={ref}>
      <IslandButton on={open} onClick={() => setOpen(!open)} title={label} aria-label={label}
                    aria-haspopup="menu" aria-expanded={open}>
        <More />
      </IslandButton>
      {open && (
        <div role="menu" aria-label={label}
             className="absolute right-0 top-[calc(100%+8px)] z-30 grid min-w-52 py-1.5 rounded-xl border border-line bg-paper shadow-menu">
          <Close.Provider value={close}>{children}</Close.Provider>
        </div>
      )}
    </div>
  );
}

/** Choices under a small heading, a line between groups. */
export function MenuGroup({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div role="group" aria-label={label} className="grid border-line not-first:mt-1.5 not-first:pt-1.5 not-first:border-t">
      <span className="px-4 pt-1 pb-1 text-[11px] font-semibold uppercase tracking-[0.05em] text-faint">{label}</span>
      {children}
    </div>
  );
}

/** One choice of a group: ✓ when it is the one on. */
export function MenuRadio({ checked, onSelect, icon, children }: {
  checked: boolean; onSelect: () => void; icon?: ReactNode; children: ReactNode;
}) {
  const close = useContext(Close);
  return (
    <button role="menuitemradio" aria-checked={checked} onClick={() => { onSelect(); close(); }}
            className={cn("flex items-center gap-2.5 px-4 py-1.75 text-[15px] text-left text-fg hover:bg-hover",
                          "[&>svg]:flex-none [&>svg]:text-muted")}>
      {icon}
      <span className="flex-1">{children}</span>
      <span className={cn("flex-none text-accent", !checked && "invisible")}><Check /></span>
    </button>
  );
}
