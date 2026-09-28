// The dialog's settings: groups of switches, choices of a few and a text field.
import type { ReactNode } from "react";
import { cn } from "@/shared/lib/cn";

const row = "grid gap-1.5 px-2 py-1.5 text-[15px]";

export function Group({ label, children }: { label: string; children: ReactNode }) {
  return (
    <section className="grid gap-1">
      <h3 className="mt-0 mb-1 text-[12px] font-semibold uppercase tracking-[0.05em] text-faint">{label}</h3>
      {children}
    </section>
  );
}

/** A setting's name over what sets it. */
export function Labelled({ label, children }: { label: string; children: ReactNode }) {
  return <div className={row}><span>{label}</span>{children}</div>;
}

/** On or off: a switch, with a hint under the name. */
export function Toggle({ label, hint, on, set, disabled }: {
  label: string; hint?: string; on: boolean; set: (on: boolean) => void; disabled?: boolean;
}) {
  return (
    <label className={cn("flex items-center justify-between gap-3 px-2 py-1.75 rounded-lg cursor-pointer text-[15px] hover:bg-selected",
                         disabled && "opacity-45 cursor-default")}>
      <span className="grid"><span>{label}</span>{hint && <small className="text-[12px] text-muted">{hint}</small>}</span>
      <input type="checkbox" role="switch" checked={on} disabled={disabled} onChange={(e) => set(e.target.checked)}
             className="appearance-none relative flex-none w-8.5 h-5 m-0 p-0 border-none rounded-full bg-line checked:bg-primary
                        cursor-[inherit] transition-colors duration-150 focus:outline-none
                        after:absolute after:top-0.5 after:left-0.5 after:size-4 after:rounded-full after:bg-white
                        after:shadow-[0_1px_2px_rgb(0_0_0/0.25)] after:transition-transform after:duration-150 checked:after:translate-x-3.5" />
    </label>
  );
}

/** One of a few: side by side, the chosen one raised. */
export function Choice<T extends string>({ label, value, set, options }: {
  label: string; value: T; set: (v: T) => void; options: [T, string][];
}) {
  return (
    <Labelled label={label}>
      <div className="flex gap-0.5 p-0.5 rounded-lg bg-hover" role="radiogroup" aria-label={label}>
        {options.map(([v, text]) => (
          <button key={v} role="radio" aria-checked={value === v} onClick={() => set(v)}
                  className="flex-1 justify-center px-2 py-1.25 whitespace-nowrap rounded-md text-[14px] text-muted
                             aria-checked:bg-surface aria-checked:text-fg aria-checked:shadow-[0_0_0_1px_var(--line)]">
            {text}
          </button>
        ))}
      </div>
    </Labelled>
  );
}

export function Field({ label, value, set, placeholder, disabled }: {
  label: string; value: string; set: (value: string) => void; placeholder?: string; disabled?: boolean;
}) {
  return (
    <label className={cn(row, disabled && "opacity-45")}>
      <span>{label}</span>
      <input value={value} placeholder={placeholder} disabled={disabled} spellCheck={false} onChange={(e) => set(e.target.value)}
             className="text-[14px] px-2.5 py-1.5 rounded-lg border border-line bg-surface text-fg focus:outline-none focus:border-fg" />
    </label>
  );
}
