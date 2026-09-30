// A menu behind an island's ⋯, like Excalidraw's: it opens under the button; a click outside, Esc or
// an action closes it. Actions on top (an icon, a name, a key); preferences under a line, each a row
// — its name, and a control beside it (a switch of icons, a drop-down).
import { createContext, type ReactNode, useCallback, useContext, useEffect, useRef, useState } from "react";
import { useClickOutside } from "@/shared/hooks/useClickOutside";
import { cn } from "@/shared/lib/cn";
import { IslandButton } from "./Island";
import { Check, More } from "./icons";

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
      <IslandButton
        on={open}
        onClick={() => setOpen(!open)}
        title={label}
        aria-label={label}
        aria-haspopup="menu"
        aria-expanded={open}
      >
        <More />
      </IslandButton>
      {open && (
        <div
          role="menu"
          aria-label={label}
          className="absolute right-0 top-[calc(100%+8px)] z-30 grid w-72 p-1.5 rounded-xl border border-line bg-paper shadow-menu"
        >
          <Close.Provider value={close}>{children}</Close.Provider>
        </div>
      )}
    </div>
  );
}

/** Choices under a small heading, a line between groups. */
export function MenuGroup({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div
      role="group"
      aria-label={label}
      className="grid border-line not-first:mt-1.5 not-first:pt-1.5 not-first:border-t"
    >
      <span className="px-4 pt-1 pb-1 text-[11px] font-semibold uppercase tracking-[0.05em] text-faint">{label}</span>
      {children}
    </div>
  );
}

/** One choice of a group: ✓ when it is the one on. */
export function MenuRadio({
  checked,
  onSelect,
  icon,
  children,
}: {
  checked: boolean;
  onSelect: () => void;
  icon?: ReactNode;
  children: ReactNode;
}) {
  const close = useContext(Close);
  return (
    <button
      role="menuitemradio"
      aria-checked={checked}
      onClick={() => {
        onSelect();
        close();
      }}
      className={cn(
        "flex items-center gap-2.5 px-4 py-1.75 text-[15px] text-left text-fg hover:bg-hover",
        "[&>svg]:flex-none [&>svg]:text-muted",
      )}
    >
      {icon}
      <span className="flex-1">{children}</span>
      <span className={cn("flex-none text-accent", !checked && "invisible")}>
        <Check />
      </span>
    </button>
  );
}

/** One action (not a choice): it runs, the menu closes. Its key, if it has one, on the right. */
export function MenuItem({
  onSelect,
  icon,
  shortcut,
  children,
}: {
  onSelect: () => void;
  icon?: ReactNode;
  shortcut?: string;
  children: ReactNode;
}) {
  const close = useContext(Close);
  return (
    <button
      role="menuitem"
      onClick={() => {
        close();
        onSelect();
      }}
      className={cn(
        "flex items-center gap-3 h-9 px-2.5 rounded-lg text-[15px] text-left text-fg hover:bg-hover",
        "[&>svg]:flex-none [&>svg]:text-fg",
      )}
    >
      {icon}
      <span className="flex-1 truncate">{children}</span>
      {shortcut && <kbd className="font-sans text-[13px] text-faint">{shortcut}</kbd>}
    </button>
  );
}

/** A line between the menu's parts. */
export const MenuSeparator = () => <hr className="my-1.5 mx-1 border-0 border-t border-line" />;

/** A preference: its name on the left, its control on the right. */
export function MenuRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 min-h-10 px-2.5 text-[15px]">
      <span className="text-fg">{label}</span>
      {children}
    </div>
  );
}

/** A choice of a few, as a row of icons (the theme): the one on filled with the accent. */
export function Segmented<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: T;
  options: { value: T; label: string; icon: ReactNode }[];
  onChange: (value: T) => void;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="flex gap-0.5 p-0.5 rounded-lg border border-line">
      {options.map((o) => (
        <button
          key={o.value}
          role="radio"
          aria-checked={o.value === value}
          title={o.label}
          aria-label={o.label}
          onClick={() => onChange(o.value)}
          className={cn(
            "inline-grid place-items-center size-8 rounded-md text-muted hover:bg-hover hover:text-fg [&_svg]:size-4.5",
            o.value === value && "bg-accent text-paper hover:bg-accent hover:text-paper",
          )}
        >
          {o.icon}
        </button>
      ))}
    </div>
  );
}

/** A choice of a few, as a drop-down (the language, the symbols). */
export function MenuSelect<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: T;
  options: { value: T; label: string }[];
  onChange: (value: T) => void;
}) {
  return (
    <select
      aria-label={label}
      value={value}
      onChange={(e) => onChange(e.target.value as T)}
      className="w-36 h-9 px-2.5 rounded-lg border border-line bg-paper text-[14px] text-fg cursor-pointer hover:bg-hover focus:outline-2 focus:outline-accent-soft"
    >
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  );
}
