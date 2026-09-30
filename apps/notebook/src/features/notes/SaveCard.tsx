// Under the save button, while the pointer is over it (or it has the keyboard): what is going on, as a
// timeline — on top the session going on now (what a save would put in, by the notes' titles), under
// it the last commits (what each changed, when, whether it is on GitHub yet), and where it all goes.
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  configured,
  connect,
  disconnect,
  type SaveDetails,
  type SaveState,
  save,
  saveDetails,
  wipe,
} from "@/features/vault";
import { cn } from "@/shared/lib/cn";

const mac = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform);
const SHOWN = 6; // changes listed in the session; the rest counted
const COMMITS = 5;

type Change = "add" | "edit" | "delete";
type Item = { change: Change; name: string; what?: string };

/** "5 min temu", "wczoraj": how long ago, in the page's language. */
function ago(time: number, language: string): string {
  const format = new Intl.RelativeTimeFormat(language, { numeric: "auto" });
  const s = (time - Date.now()) / 1000;
  const units: [number, number, Intl.RelativeTimeFormatUnit][] = [
    [60, 1, "second"],
    [3600, 60, "minute"],
    [86400, 3600, "hour"],
    [604800, 86400, "day"],
    [2629800, 604800, "week"],
    [31557600, 2629800, "month"],
  ];
  if (Math.abs(s) < 45) return format.format(0, "second");
  for (const [below, size, unit] of units) if (Math.abs(s) < below) return format.format(Math.round(s / size), unit);
  return format.format(Math.round(s / 31557600), "year");
}

/** A commit's message as the vault writes it — `Edit "A", "B"; add "C" and 2 more` — back into what
 *  it changed (null: a message of some other kind, shown as it is). */
function parse(message: string): { items: Item[]; more: number } | null {
  const items: Item[] = [];
  let more = 0;
  for (const part of message.split("; ")) {
    const m = /^(edit|add|delete) (.*)$/i.exec(part);
    if (!m) return null;
    const change = m[1].toLowerCase() as Change;
    for (const t of m[2].matchAll(/"([^"]*)"/g)) items.push({ change, name: t[1] });
    more += Number(/and (\d+) more$/.exec(m[2])?.[1] ?? 0);
  }
  return items.length ? { items, more } : null;
}

const SIGN: Record<Change, string> = { add: "+", edit: "~", delete: "−" };
const TONE: Record<Change, string> = { add: "text-ok", edit: "text-accent", delete: "text-danger" };

function Chip({ item, unnamed }: { item: Item; unnamed: string }) {
  return (
    <span className="inline-flex items-baseline gap-1 max-w-full min-w-0 px-1.5 py-px rounded-md bg-hover">
      <span className={cn("font-mono font-medium", TONE[item.change])}>{SIGN[item.change]}</span>
      <span className={cn("truncate", item.change === "delete" && "line-through decoration-faint")}>
        {item.what && <span className="text-muted">{item.what} </span>}
        {item.name || (item.what ? "" : unnamed)}
      </span>
    </span>
  );
}

/** A step on the timeline: its dot, and what is beside it. */
function Step({
  dot,
  last,
  children,
}: {
  dot: "now" | "local" | "remote" | "saved";
  last?: boolean;
  children: React.ReactNode;
}) {
  return (
    <li className="relative grid grid-cols-[14px_1fr] gap-x-2.5">
      {!last && <span aria-hidden className="absolute left-[6px] top-3.5 bottom-[-6px] w-px bg-line" />}
      <span
        aria-hidden
        className={cn(
          "relative mt-1 size-3.5 rounded-full border-2",
          dot === "now" && "border-accent bg-accent-soft",
          dot === "local" && "border-warn bg-paper",
          dot === "remote" && "border-ok bg-ok",
          dot === "saved" && "border-faint bg-faint",
        )}
      />
      <div className="grid gap-1 min-w-0 pb-3">{children}</div>
    </li>
  );
}

// the last details read: the card opens with them at once (no jump), then reads them afresh
let lastRead: SaveDetails | null = null;

export function SaveCard({ state, onSave }: { state: SaveState; onSave: () => void }) {
  const { t, i18n } = useTranslation("notes", { keyPrefix: "save.card" });
  const { t: ta } = useTranslation("auth");

  /** Disconnecting GitHub: everything saved there first; then the notes here kept, or wiped. */
  const leave = async () => {
    if (!confirm(ta("confirmDisconnect"))) return;
    // (a save that does not come back in half a minute counts as not done)
    const saved = await Promise.race([save(), new Promise<false>((r) => setTimeout(() => r(false), 30_000))]);
    if (!saved && !confirm(ta("notSaved"))) return;
    if (confirm(ta("wipe"))) {
      await wipe();
      localStorage.removeItem("electro.vault-owner");
    }
    disconnect();
    location.reload();
  };
  const [details, setDetails] = useState<SaveDetails | null>(lastRead);
  const [failed, setFailed] = useState(false);

  // read when shown, and again whenever saving moves on
  useEffect(() => {
    let alive = true;
    saveDetails().then(
      (d) => {
        lastRead = d;
        if (alive) {
          setDetails(d);
          setFailed(false);
        }
      },
      (e) => {
        console.warn("The save details could not be read", e);
        if (alive) setFailed(true);
      },
    );
    return () => {
      alive = false;
    };
  }, [state.pending, state.open, state.saving]);

  const dirty = state.pending || state.open || (details?.changes.length ?? 0) > 0;
  const status = state.saving
    ? t("saving")
    : state.pending
      ? t("pending")
      : state.open && details?.autosaved
        ? t("open", { when: ago(details.autosaved, i18n.language) })
        : t("allSaved");
  const history = details?.history.slice(0, COMMITS) ?? [];

  return (
    <div
      role="dialog"
      aria-label={t("label")}
      className="absolute top-full right-0 mt-2 w-84 max-sm:fixed max-sm:top-17 max-sm:inset-x-3 max-sm:mt-0 max-sm:w-auto z-50 grid gap-3 p-4 rounded-2xl border border-line bg-paper shadow-menu text-[13px] text-left cursor-default"
    >
      <div className="flex items-center gap-2">
        <span
          aria-hidden
          className={cn("size-2 rounded-full", state.saving ? "bg-accent animate-blink" : dirty ? "bg-warn" : "bg-ok")}
        />
        <span className="text-[14px] font-medium">{status}</span>
      </div>
      {failed && <p className="m-0 text-danger">{t("unreadable")}</p>}
      {details && (
        <ol className="m-0 p-0 list-none">
          <Step dot="now" last={!history.length}>
            <div className="flex items-baseline gap-2">
              <span className="font-medium">{t("now")}</span>
              <span className="text-faint">{details.changes.length ? t("notSaved") : t("noChanges")}</span>
            </div>
            {details.changes.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {details.changes.slice(0, SHOWN).map((c, i) => (
                  <Chip
                    key={i}
                    unnamed={t("unnamed")}
                    item={{
                      change: c.change,
                      name: c.what === "note" || c.what === "component" ? c.name : "",
                      what: c.what === "note" ? undefined : t(`what.${c.what}`),
                    }}
                  />
                ))}
                {details.changes.length > SHOWN && (
                  <span className="px-1 text-muted">{t("more", { count: details.changes.length - SHOWN })}</span>
                )}
              </div>
            )}
          </Step>
          {history.map((c, i) => {
            const parsed = parse(c.message);
            return (
              <Step
                key={c.oid}
                dot={details.github ? (c.onGitHub ? "remote" : "local") : "saved"}
                last={i === history.length - 1}
              >
                <div className="flex items-baseline gap-2 min-w-0">
                  <span className="font-medium whitespace-nowrap">{ago(c.time, i18n.language)}</span>
                  <span className="font-mono text-[11px] text-faint">{c.oid.slice(0, 7)}</span>
                  {details.github && (
                    <span className={cn("ml-auto text-[11px] whitespace-nowrap", c.onGitHub ? "text-ok" : "text-warn")}>
                      {c.onGitHub ? t("onGitHub") : t("localOnly")}
                    </span>
                  )}
                </div>
                {parsed ? (
                  <div className="flex flex-wrap gap-1">
                    {parsed.items.map((item, k) => (
                      <Chip key={k} item={item} unnamed={t("unnamed")} />
                    ))}
                    {parsed.more > 0 && <span className="px-1 text-muted">{t("more", { count: parsed.more })}</span>}
                  </div>
                ) : (
                  <span className="text-muted truncate" title={c.message}>
                    {c.message}
                  </span>
                )}
              </Step>
            );
          })}
        </ol>
      )}
      <div className="grid gap-2 pt-3 border-t border-line">
        <button
          className="inline-flex items-center justify-center gap-2 w-full h-9 rounded-lg bg-primary text-on-primary text-[14px] font-medium hover:bg-primary-hover disabled:opacity-50"
          disabled={state.saving}
          onClick={onSave}
        >
          {state.saving ? t("saving") : t("saveNow")}
          <kbd className="font-sans text-[12px] opacity-70 pointer-coarse:hidden">{mac ? "⌘S" : "Ctrl+S"}</kbd>
        </button>
        {details?.github ? (
          <div className="grid justify-items-center gap-1 text-center text-[12px] text-muted leading-snug">
            <span className="min-w-0 break-words">
              {t("github")}{" "}
              <a
                className="font-mono text-accent no-underline hover:underline whitespace-nowrap"
                href={details.github.url}
                target="_blank"
                rel="noreferrer"
              >
                {details.github.login}/electro-notes
              </a>
            </span>
            <button className="text-faint hover:text-danger" onClick={() => void leave()}>
              {ta("disconnect")}
            </button>
          </div>
        ) : (
          details && (
            <>
              {configured() && (
                <button
                  className="w-full h-9 rounded-lg border border-line text-[14px] hover:bg-hover"
                  onClick={() => connect(location.pathname + location.search)}
                >
                  {t("connect")}
                </button>
              )}
              <span className="text-[12px] text-muted leading-snug">{t("local")}</span>
            </>
          )
        )}
      </div>
    </div>
  );
}

/** Read the details ahead of the card's first opening (so even that one does not jump). */
export function readSaveDetails() {
  saveDetails().then(
    (d) => {
      lastRead = d;
    },
    () => {},
  );
}
