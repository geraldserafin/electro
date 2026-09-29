// A panel floating over the board, as Excalidraw's properties panel: a card with a soft shadow,
// sections each under a plain small label, square tiles for choices and actions (the chosen one
// tinted with the accent). The element library, the inspector and the meter are made of these.
import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode } from "react";
import { cn } from "@/shared/lib/cn";
import { Close } from "@/shared/ui/icons";
import { BoardIsland } from "./Board";

export function Panel({ className, children, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <BoardIsland stays {...props} className={cn("flex-col items-stretch gap-4 p-3.5 rounded-xl overflow-hidden", className)}>
      {children}
    </BoardIsland>
  );
}

/** A panel's head: an icon, a small caption over a name, what it can do (close, …). */
export function PanelHead({ icon, caption, title, onClose, closeLabel, children }: {
  icon?: ReactNode; caption: ReactNode; title?: ReactNode; onClose?: () => void; closeLabel?: string; children?: ReactNode;
}) {
  return (
    <header className="flex items-center gap-2.5 min-w-0">
      {icon && <span className="grid place-items-center flex-none size-10 rounded-lg bg-hover text-fg">{icon}</span>}
      <div className="grid flex-1 min-w-0">
        <span className="text-[13px] text-muted truncate">{caption}</span>
        {title && <span className="text-[16px] font-semibold truncate">{title}</span>}
      </div>
      {children}
      {onClose && (
        <Tile className="size-8 bg-transparent" onClick={onClose} title={closeLabel} aria-label={closeLabel}><Close /></Tile>
      )}
    </header>
  );
}

/** A section: a plain label, what it holds under it. */
export function Section({ label, children, className }: { label: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={cn("grid gap-2", className)}>
      <h4 className="m-0 text-[13px] font-normal text-muted">{label}</h4>
      {children}
    </section>
  );
}

/** A square tile: a choice (``on``: chosen, tinted) or an action. */
export function Tile({ on, className, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { on?: boolean }) {
  return (
    <button {...props}
            className={cn("relative inline-grid place-items-center flex-none size-9 rounded-lg bg-hover text-fg hover:bg-selected disabled:opacity-40 [&_svg]:size-4",
                          on && "bg-accent-soft text-accent hover:bg-accent-soft outline-1 outline-accent/40", className)} />
  );
}

/** A text field on a panel (and its unit inside, on the right). */
export const field = "w-full h-9 px-2.5 rounded-lg border border-transparent bg-hover text-[14px] focus:bg-paper focus:outline-2 focus:outline-accent-soft";
