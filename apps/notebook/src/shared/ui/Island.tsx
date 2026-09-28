// The app's chrome: no bar, islands floating over the page (like Excalidraw) — in the top corners,
// a row each. data-keep-focus: a click on them does not leave the cell being worked on.
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { Link, type LinkProps } from "react-router";
import { Bolt } from "./icons";

const corner = { left: "left-3", right: "right-3" };

/** A row of islands in a top corner of the page. */
export function Islands({ side, children }: { side: "left" | "right"; children: ReactNode }) {
  return <div data-keep-focus className={`fixed top-3 z-20 flex gap-2 ${corner[side]}`}>{children}</div>;
}

/** An island: a flat tile one step off the page, holding a few things in a row. */
export function Island({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`flex items-center gap-0.5 p-1 rounded-xl border border-line bg-surface ${className}`}>{children}</div>
  );
}

// an island that is one button (or link); `on`: its panel is open
const button = (on?: boolean) =>
  "inline-flex flex-none items-center justify-center size-11.5 p-0 rounded-xl border border-line text-fg no-underline " +
  `hover:bg-selected ${on ? "bg-selected" : "bg-surface"}`;

export function IslandButton({ on, waiting, className = "", ...props }: ButtonHTMLAttributes<HTMLButtonElement> & {
  on?: boolean;
  waiting?: boolean; // what it does is not ready yet (Python is starting): it blinks
}) {
  return <button {...props} className={`${button(on)} ${waiting ? "animate-blink" : ""} ${className}`} />;
}

export function IslandLink(props: LinkProps) {
  return <Link {...props} className={button()} />;
}

/** The bolt and the app's name. */
export function Brand({ title }: { title?: string }) {
  return (
    <Island>
      <span className="grid place-items-center size-8 flex-none rounded-lg text-[#f9ab00]" title={title}><Bolt /></span>
      <span className="pr-2.5 pl-0.5 text-[17px] font-medium">electro</span>
    </Island>
  );
}
