// A choice that shows as its text with a chevron (Notion's "Can edit ▾"), and opens a small menu
// under it: each option with a line saying what it means, ✓ at the one chosen; below a line,
// actions (such as "Remove", in red). A press outside or Esc closes it (Esc: only it, not a dialog
// around it).
import { type ReactNode, useCallback, useEffect, useRef, useState } from "react";
import { cn } from "@/shared/lib/cn";
import { Check, Chevron } from "./icons";

export type PickerOption<T extends string> = { value: T; label: string; description?: string; icon?: ReactNode };
export type PickerAction = { label: string; description?: string; danger?: boolean; run: () => void };

export function Picker<T extends string>({
  value,
  options,
  actions = [],
  onChange,
  label,
  align = "right",
  className,
  children,
}: {
  value: T;
  options: PickerOption<T>[];
  actions?: PickerAction[];
  onChange: (value: T) => void;
  label: string; // for a screen reader: what is being chosen
  align?: "left" | "right"; // the menu's edge, at the button's
  className?: string;
  children?: ReactNode; // the button's content (else: the chosen option's label)
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const close = useCallback(() => setOpen(false), []);
  const chosen = options.find((o) => o.value === value);

  useEffect(() => {
    if (!open) return;
    const press = (e: PointerEvent) => {
      if (!ref.current?.contains(e.target as Node)) close();
    };
    const esc = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        close();
        button.current?.focus();
      }
    };
    document.addEventListener("pointerdown", press);
    window.addEventListener("keydown", esc, true);
    return () => {
      document.removeEventListener("pointerdown", press);
      window.removeEventListener("keydown", esc, true);
    };
  }, [open, close]);

  const row = "flex items-start gap-2.5 w-full px-3 py-1.75 rounded-md text-left hover:bg-hover";
  return (
    <span ref={ref} className="relative inline-flex">
      <button
        ref={button}
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`${label}: ${chosen?.label ?? value}`}
        onClick={() => setOpen(!open)}
        className={cn(
          "inline-flex items-center gap-1 h-8 px-2 rounded-md text-[14px] text-muted whitespace-nowrap hover:bg-hover aria-expanded:bg-hover",
          className,
        )}
      >
        {children ?? chosen?.label}
        <Chevron />
      </button>
      {open && (
        <div
          role="menu"
          aria-label={label}
          className={cn(
            "absolute top-[calc(100%+6px)] z-30 grid w-max max-w-80 min-w-56 p-1 rounded-lg border border-line bg-paper shadow-menu",
            align === "right" ? "right-0" : "left-0",
          )}
        >
          {options.map((o) => (
            <button
              key={o.value}
              type="button"
              role="menuitemradio"
              aria-checked={o.value === value}
              className={row}
              onClick={() => {
                close();
                if (o.value !== value) onChange(o.value);
              }}
            >
              {o.icon && <span className="mt-0.5 flex-none text-muted">{o.icon}</span>}
              <span className="grid flex-1">
                <span className="text-[14px] text-fg">{o.label}</span>
                {o.description && <span className="text-[12px] leading-snug text-muted">{o.description}</span>}
              </span>
              <span className={cn("mt-0.5 flex-none text-fg", o.value !== value && "invisible")}>
                <Check />
              </span>
            </button>
          ))}
          {actions.length > 0 && <div className="my-1 border-t border-line" />}
          {actions.map((a) => (
            <button
              key={a.label}
              type="button"
              role="menuitem"
              className={row}
              onClick={() => {
                close();
                a.run();
              }}
            >
              <span className="grid flex-1">
                <span className={cn("text-[14px]", a.danger ? "text-danger" : "text-fg")}>{a.label}</span>
                {a.description && <span className="text-[12px] leading-snug text-muted">{a.description}</span>}
              </span>
            </button>
          ))}
        </div>
      )}
    </span>
  );
}
