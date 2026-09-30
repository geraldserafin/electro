// The app's chrome: no bar, islands floating over the page (like Excalidraw) — in the top corners,
// a row each. data-keep-focus: a click on them does not leave the cell being worked on.
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { Link, type LinkProps } from "react-router";
import { cn } from "@/shared/lib/cn";

const corner = { left: "left-3", right: "right-3" };

/** A row of islands in a top corner of the page. */
export function Islands({ side, children }: { side: "left" | "right"; children: ReactNode }) {
  return (
    <div data-keep-focus className={cn("fixed top-3 z-20 flex gap-2", corner[side])}>
      {children}
    </div>
  );
}

/** An island: a flat tile one step off the page, holding a few things in a row. */
export function Island({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn("flex items-center gap-0.5 p-1 rounded-xl border border-line bg-surface", className)}>
      {children}
    </div>
  );
}

// an island that is one button (or link); `on`: its panel is open
const button = (on?: boolean) =>
  cn(
    "inline-flex flex-none items-center justify-center size-11.5 rounded-xl border border-line bg-surface text-fg no-underline",
    "hover:bg-selected",
    on && "bg-selected",
  );

export function IslandButton({
  on,
  waiting,
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  on?: boolean;
  waiting?: boolean; // what it does is not ready yet (Python is starting): it blinks
}) {
  return <button {...props} className={cn(button(on), waiting && "animate-blink", className)} />;
}

export function IslandLink(props: LinkProps) {
  return <Link {...props} className={button()} />;
}

/** Who made it, and how to reach him: a quiet line at the bottom of the home page. */
export const AUTHOR = {
  name: "Gerald Serafin",
  links: [
    { label: "GitHub", href: "https://github.com/geraldserafin" },
    { label: "LinkedIn", href: "https://www.linkedin.com/in/gerald-serafin/" },
    { label: "serafingerald@protonmail.com", href: "mailto:serafingerald@protonmail.com" },
  ],
};

export function Credits({ madeBy }: { madeBy: string }) {
  return (
    <footer className="mt-20 flex flex-wrap items-center justify-center gap-x-3 gap-y-1 font-mono text-[12px] text-faint">
      <span>
        {madeBy} <span className="text-muted">{AUTHOR.name}</span>
      </span>
      {AUTHOR.links.map((l) => (
        <span key={l.href} className="flex items-center gap-3">
          <span aria-hidden>·</span>
          <a
            className="text-faint no-underline hover:text-fg"
            href={l.href}
            target={l.href.startsWith("http") ? "_blank" : undefined}
            rel="noreferrer"
          >
            {l.label}
          </a>
        </span>
      ))}
    </footer>
  );
}
