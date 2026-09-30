// Bottom right, while the tools are downloading (Python, the compiler, a board's libraries: tens of
// MB, once): a bolt filling up with yellow as they come. Over it (or clicked), what is coming, how
// far along. It stays a moment after the last is done, full, then goes.
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { cn } from "@/shared/lib/cn";
import { groups, useDownloads } from "./store";

const BOLT = "M13 2L4 14h7l-1 8 9-12h-7z";
const LINGER = 2500; // ms it stays, full, after the last download
const SLOW = 400; // ms a download must take to be shown at all (from the browser's cache it takes less)

const mb = (bytes: number) => `${(bytes / 1e6).toFixed(bytes < 1e7 ? 1 : 0)} MB`;

export function Downloads() {
  const { t } = useTranslation("downloads");
  const all = groups(useDownloads());
  const busy = all.some((g) => !g.done);
  const [shown, setShown] = useState(false);
  const [open, setOpen] = useState(false); // the list: over it, or clicked
  const [pinned, setPinned] = useState(false);
  const timer = useRef<number | undefined>(undefined);

  // shown while anything downloads — unless it is over at once (the browser had it) — and a moment after
  useEffect(() => {
    clearTimeout(timer.current);
    if (busy && !shown) timer.current = window.setTimeout(() => setShown(true), SLOW);
    else if (!busy && shown && !open && !pinned) timer.current = window.setTimeout(() => setShown(false), LINGER);
    return () => clearTimeout(timer.current);
  }, [busy, open, pinned, shown]);

  if (!shown || !all.length) return null;
  const weight = all.reduce((s, g) => s + Math.max(g.total, 1), 0);
  const fraction = all.reduce((s, g) => s + g.fraction * Math.max(g.total, 1), 0) / weight;
  const id = "downloads-bolt";

  return (
    <div
      data-keep-focus
      className="fixed bottom-4 right-4 z-30 animate-fade-in"
      onPointerEnter={() => setOpen(true)}
      onPointerLeave={() => setOpen(false)}
    >
      {(open || pinned) && (
        <div
          role="status"
          className="absolute bottom-full right-0 mb-2 w-76 grid gap-3 p-4 rounded-2xl border border-line bg-paper shadow-menu text-[13px]"
        >
          <div className="text-[14px] font-medium">{t("title")}</div>
          <ul className="m-0 p-0 list-none grid gap-3">
            {all.map((g) => (
              <li key={g.group} className="grid gap-1.5">
                <div className="flex items-baseline gap-2">
                  <span className="truncate">{t(`groups.${g.group}` as "groups.python", g.group)}</span>
                  <span className={cn("ml-auto whitespace-nowrap text-[12px]", g.error ? "text-danger" : "text-faint")}>
                    {g.error ? t("failed") : g.done ? t("done") : `${Math.round(g.fraction * 100)}%`}
                  </span>
                </div>
                <div className="h-1.5 rounded-full bg-hover overflow-hidden">
                  <div
                    className={cn(
                      "h-full rounded-full transition-[width] duration-200",
                      g.error ? "bg-danger" : g.done ? "bg-ok" : "bg-[#f9ab00]",
                    )}
                    style={{ width: `${Math.max(3, g.fraction * 100)}%` }}
                  />
                </div>
                <span className="font-mono text-[11px] text-faint">
                  {g.done || !g.known ? mb(g.loaded) : t("of", { loaded: mb(g.loaded), total: mb(g.total) })} ·{" "}
                  {t("files", { count: g.files })}
                </span>
              </li>
            ))}
          </ul>
          <p className="m-0 text-[12px] text-faint leading-snug">{t("hint")}</p>
        </div>
      )}
      <button
        className="grid place-items-center size-11.5 rounded-xl border border-line bg-surface hover:bg-selected"
        aria-label={`${t("label")}: ${Math.round(fraction * 100)}%`}
        aria-expanded={open || pinned}
        onClick={() => setPinned(!pinned)}
      >
        <svg viewBox="0 0 24 24" className="size-6" aria-hidden>
          <defs>
            <clipPath id={id}>
              <path d={BOLT} />
            </clipPath>
          </defs>
          <path d={BOLT} className="fill-line" />
          <g clipPath={`url(#${id})`}>
            <rect
              x={0}
              y={0}
              width={24}
              height={24 * fraction}
              fill="#f9ab00"
              className="transition-[height] duration-300"
            />
          </g>
        </svg>
      </button>
    </div>
  );
}
