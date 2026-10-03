// The assistant, beside the note: a conversation on the right (as the outline is on the left), opened
// by the sparkle in the bottom right corner. What is asked — text, pictures pasted or dropped, a
// PDF's pages — goes to the agent (agent.ts) with the note as it is; what it does with its tools goes
// into the note as it goes (after the cell worked on), each turn's changes with a way back. It asks
// OpenRouter with the user's own key (the gear: the key and the model); on top, what this conversation cost.
import { type DragEvent, type KeyboardEvent, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { cn } from "@/shared/lib/cn";
import type { Cell } from "@/shared/model/types";
import { ArrowUp, Close, Gear, NewChat, Paperclip, Sparkle } from "@/shared/ui/icons";
import { Markdown } from "@/shared/ui/Markdown";
import { type Doing, turn } from "./agent";
import { accepts, MAX_PICTURES, picturesOf } from "./attachments";
import { AiError, type AiMessage, aiSettings, DEFAULT_MODEL, type Progress, saveAiSettings } from "./client";

type Change = { added: number; changed: number };

type Entry =
  | { kind: "user"; text: string; pictures: string[] }
  | { kind: "assistant"; text: string; change: Change; before: Cell[]; undone?: boolean }
  | { kind: "error"; text: string };

const ease = "ease-[cubic-bezier(0.2,0.8,0.2,1)] duration-250 motion-reduce:transition-none";
const iconButton =
  "inline-flex flex-none items-center justify-center size-8 rounded-lg text-muted hover:bg-selected hover:text-fg disabled:opacity-40 [&_svg]:size-4";

/** The sparkle in the bottom right corner: the assistant, open or closed. */
export function AiButton({ open, onToggle }: { open: boolean; onToggle: () => void }) {
  const { t } = useTranslation("ai");
  return (
    <button
      data-keep-focus
      className={cn(
        "fixed right-4 bottom-4 z-30 grid place-items-center size-11.5 rounded-xl border border-line shadow-tools [&_svg]:size-5",
        open ? "bg-accent text-white border-accent" : "bg-surface text-accent hover:bg-selected",
      )}
      onClick={onToggle}
      aria-pressed={open}
      title={t("button")}
      aria-label={t("button")}
    >
      <Sparkle />
    </button>
  );
}

export function AiChat({
  open,
  onClose,
  cells,
  setCells,
  at,
}: {
  open: boolean;
  onClose: () => void;
  cells: () => Cell[]; // the note's cells now
  setCells: (cells: Cell[]) => void;
  at: () => number; // where new cells go
}) {
  const { t, i18n } = useTranslation("ai");
  const [entries, setEntries] = useState<Entry[]>([]);
  const [history, setHistory] = useState<AiMessage[]>([]); // the agent's conversation, its tools' too
  const [seen, setSeen] = useState<string[]>([]); // the conversation's pictures, by number (from 1)
  const [text, setText] = useState("");
  const [pictures, setPictures] = useState<string[]>([]);
  const [step, setStep] = useState<"asking" | null>(null);
  const [live, setLive] = useState<Progress | null>(null); // the model's writing, as it comes
  const [doing, setDoing] = useState<Doing[]>([]); // the tools it used this turn
  const [dragging, setDragging] = useState(false);
  const [cost, setCost] = useState(0); // this conversation's, in dollars
  const [keying, setKeying] = useState(() => !aiSettings().key); // the key's and the model's form, open
  const list = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);
  const files = useRef<HTMLInputElement>(null);

  // the newest at the bottom, in view
  useEffect(() => {
    list.current?.scrollTo({ top: list.current.scrollHeight, behavior: "smooth" });
  }, [entries, step]);
  useEffect(() => {
    if (open) input.current?.focus();
  }, [open]);

  const attach = async (picked: Iterable<File>) => {
    try {
      const got = await picturesOf([...picked].filter(accepts), MAX_PICTURES - pictures.length);
      setPictures((now) => [...now, ...got].slice(0, MAX_PICTURES));
    } catch {
      setEntries((now) => [...now, { kind: "error", text: t("pdfFailed") }]);
    }
  };

  // a picture pasted while the conversation is open
  useEffect(() => {
    if (!open) return;
    const paste = (e: ClipboardEvent) => {
      const pasted = [...(e.clipboardData?.items ?? [])].flatMap((i) => (i.kind === "file" ? [i.getAsFile()!] : []));
      if (pasted.some(accepts)) {
        e.preventDefault();
        void attach(pasted);
      }
    };
    window.addEventListener("paste", paste);
    return () => window.removeEventListener("paste", paste);
  });

  const send = async (asked = text) => {
    if (step || (!asked.trim() && !pictures.length)) return;
    const before = cells();
    const all = [...seen, ...pictures];
    setEntries((now) => [...now, { kind: "user", text: asked, pictures }]);
    setText("");
    setPictures([]);
    setSeen(all);
    setStep("asking");
    try {
      const got = await turn({
        asked,
        attached: pictures.map((_, i) => seen.length + i + 1),
        pictures: all,
        history,
        cells: before,
        at: at(),
        language: i18n.language,
        onCells: setCells,
        onDoing: setDoing,
        onProgress: setLive,
      });
      setHistory(got.history);
      setEntries((now) => [
        ...now,
        { kind: "assistant", text: got.message, change: { added: got.added, changed: got.changed }, before },
      ]);
      setCost((now) => now + got.cost);
    } catch (e) {
      const reason = e instanceof AiError ? e.reason : "failed";
      if (reason === "NoKey" || reason === "BadKey") setKeying(true);
      setEntries((now) => [...now, { kind: "error", text: t(`error.${reason}`) }]);
    } finally {
      setStep(null);
      setLive(null);
      setDoing([]);
    }
  };

  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      void send();
    }
  };
  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    void attach(e.dataTransfer.files);
  };
  const lastAssistant = entries.reduce((last, e, i) => (e.kind === "assistant" ? i : last), -1);

  return (
    <aside
      data-keep-focus
      aria-label={t("title")}
      inert={!open}
      className={cn(
        "fixed top-17 right-3 bottom-18 z-20 w-100 max-sm:left-3 max-sm:w-auto flex flex-col overflow-hidden rounded-xl border border-line bg-surface",
        `transition-[opacity,translate,visibility] ${ease}`,
        open ? "" : "invisible opacity-0 translate-x-3",
      )}
      onDragOver={(e) => {
        if ([...e.dataTransfer.items].some((i) => i.kind === "file")) {
          e.preventDefault();
          setDragging(true);
        }
      }}
      onDragLeave={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node)) setDragging(false);
      }}
      onDrop={onDrop}
    >
      <header className="flex flex-none items-center gap-1 h-11 pl-3.5 pr-1.5 border-b border-line">
        <span className="text-accent [&_svg]:size-4">
          <Sparkle />
        </span>
        <h2 className="m-0 ml-1.5 text-[15px] font-medium">{t("title")}</h2>
        {cost > 0 && (
          <span className="ml-2 text-[12px] text-faint tabular-nums" title={t("cost")}>
            ${cost < 0.01 ? cost.toFixed(4) : cost.toFixed(2)}
          </span>
        )}
        <span className="flex-1" />
        <button
          className={iconButton}
          disabled={!entries.length || step !== null}
          onClick={() => {
            setEntries([]);
            setHistory([]);
            setSeen([]);
            setCost(0);
          }}
          title={t("newChat")}
          aria-label={t("newChat")}
        >
          <NewChat />
        </button>
        <button
          className={iconButton}
          aria-pressed={keying}
          onClick={() => setKeying((now) => !now)}
          title={t("key.title")}
          aria-label={t("key.title")}
        >
          <Gear />
        </button>
        <button className={iconButton} onClick={onClose} title={t("close")} aria-label={t("close")}>
          <Close />
        </button>
      </header>

      <div ref={list} data-chat className="flex-1 min-h-0 overflow-y-auto px-3.5 py-3 grid content-start gap-3">
        {keying && <KeyForm onDone={() => setKeying(false)} />}
        {!entries.length && !keying && (
          <div className="grid gap-3 pt-2">
            <p className="m-0 text-[14px] leading-relaxed text-muted">{t("intro")}</p>
            <div className="grid gap-1.5">
              {(t("suggestions", { returnObjects: true }) as string[]).map((s) => (
                <button
                  key={s}
                  className="text-left px-3 py-2 rounded-lg border border-line bg-paper text-[13px] hover:bg-hover"
                  onClick={() => {
                    setText(s);
                    input.current?.focus();
                  }}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
        {entries.map((e, i) =>
          e.kind === "user" ? (
            <div key={i} data-entry="user" className="justify-self-end max-w-[85%] grid gap-1.5 justify-items-end">
              {e.pictures.length > 0 && (
                <div className="flex flex-wrap justify-end gap-1.5">
                  {e.pictures.map((url) => (
                    <img key={url.slice(-32)} src={url} alt="" className="h-16 rounded-md border border-line" />
                  ))}
                </div>
              )}
              {e.text && (
                <div className="px-3 py-2 rounded-xl rounded-br-sm bg-selected text-[14px] whitespace-pre-wrap">
                  {e.text}
                </div>
              )}
            </div>
          ) : e.kind === "assistant" ? (
            <div key={i} data-entry="assistant" className="grid gap-1.5 text-[14px]">
              {e.text && <Markdown source={e.text} />}
              {(e.change.added > 0 || e.change.changed > 0) && (
                <div className="flex flex-wrap items-center gap-2 text-[13px]">
                  <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-accent-soft text-accent">
                    {[
                      e.change.added ? t("added", { count: e.change.added }) : null,
                      e.change.changed ? t("changed", { count: e.change.changed }) : null,
                    ]
                      .filter(Boolean)
                      .join(", ")}
                  </span>
                  {i === lastAssistant &&
                    (e.undone ? (
                      <span className="text-faint">{t("undone")}</span>
                    ) : (
                      <button
                        className="text-muted underline-offset-2 hover:underline hover:text-fg"
                        onClick={() => {
                          setCells(e.before);
                          setEntries((now) => now.map((x, k) => (k === i ? { ...e, undone: true } : x)));
                        }}
                      >
                        {t("undo")}
                      </button>
                    ))}
                </div>
              )}
            </div>
          ) : (
            <div key={i} role="alert" className="grid gap-1.5 justify-items-start text-[13px] text-danger">
              <p className="m-0">{e.text}</p>
            </div>
          ),
        )}
        {step && (
          <div role="status" className="grid gap-1.5">
            {doing.length > 0 && (
              <ul className="m-0 p-0 grid gap-1 list-none text-[12px] text-muted">
                {doing.map((d, k) => (
                  <li key={k} className="grid">
                    <span>
                      {t(`doing.${d.tool}`, { defaultValue: d.tool, name: d.name ?? "" })}
                      {d.done ? " ✓" : ""}
                    </span>
                    {d.issue && !d.done && (
                      <span className="truncate text-faint" title={d.issue}>
                        {d.issue}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            )}
            <p className="m-0 flex items-center gap-2 text-[13px] text-muted">
              <span className="size-1.5 rounded-full bg-accent animate-pulse" />
              {t("thinking")}
            </p>
            {live && <Live progress={live} />}
          </div>
        )}
      </div>

      <div className="flex-none p-2.5 border-t border-line">
        <div
          className={cn(
            "grid gap-2 p-2 rounded-xl border bg-paper transition-colors",
            dragging ? "border-accent bg-accent-soft" : "border-line focus-within:border-accent",
          )}
        >
          {pictures.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {pictures.map((url, i) => (
                <span key={url.slice(-32)} className="relative">
                  <img src={url} alt="" className="h-14 rounded-md border border-line" />
                  <button
                    className="absolute -top-1.5 -right-1.5 grid place-items-center size-5 rounded-full border border-line bg-surface text-muted hover:text-fg [&_svg]:size-3"
                    onClick={() => setPictures((now) => now.filter((_, k) => k !== i))}
                    aria-label={t("remove")}
                  >
                    <Close />
                  </button>
                </span>
              ))}
            </div>
          )}
          <textarea
            ref={input}
            rows={1}
            value={text}
            placeholder={dragging ? t("drop") : t("placeholder")}
            aria-label={t("placeholder")}
            className="w-full max-h-40 resize-none bg-transparent text-[14px] outline-none [field-sizing:content]"
            onChange={(e) => setText(e.target.value)}
            onKeyDown={onKey}
          />
          <div className="flex items-center gap-1">
            <button
              className={iconButton}
              onClick={() => files.current?.click()}
              disabled={pictures.length >= MAX_PICTURES}
              title={t("attach")}
              aria-label={t("attach")}
            >
              <Paperclip />
            </button>
            <input
              ref={files}
              type="file"
              accept="image/*,application/pdf"
              multiple
              hidden
              onChange={(e) => {
                if (e.target.files) void attach(e.target.files);
                e.target.value = "";
              }}
            />
            <span className="flex-1" />
            <button
              className="inline-flex items-center justify-center size-8 rounded-lg bg-primary text-on-primary hover:bg-primary-hover disabled:opacity-40 [&_svg]:size-4"
              disabled={step !== null || (!text.trim() && !pictures.length)}
              onClick={() => void send()}
              title={t("send")}
              aria-label={t("send")}
            >
              <ArrowUp />
            </button>
          </div>
        </div>
      </div>
    </aside>
  );
}

/** The model's writing as it comes: its message taking shape, else the end of its thinking (faded). */
function Live({ progress }: { progress: Progress }) {
  if (progress.content.trim()) return <Markdown source={progress.content} />;
  const thought = progress.thinking.trim();
  if (!thought) return null;
  return (
    <p className="m-0 max-h-16 overflow-hidden text-[12px] leading-snug text-faint italic [mask-image:linear-gradient(to_bottom,transparent,black_40%)] flex flex-col justify-end">
      {thought.slice(-280)}
    </p>
  );
}

/** The user's OpenRouter key and the model, kept in this browser. */
function KeyForm({ onDone }: { onDone: () => void }) {
  const { t } = useTranslation("ai");
  const [settings, setSettings] = useState(aiSettings);
  const field = "w-full h-8 px-2.5 rounded-lg border border-line bg-paper text-[13px] outline-none focus:border-accent";
  return (
    <form
      className="grid gap-2.5 p-3 rounded-xl border border-line bg-paper text-[13px]"
      onSubmit={(e) => {
        e.preventDefault();
        saveAiSettings(settings);
        if (settings.key.trim()) onDone();
      }}
    >
      <p className="m-0 leading-relaxed text-muted">
        {t("key.intro")}{" "}
        <a href="https://openrouter.ai/keys" target="_blank" rel="noreferrer" className="text-accent underline">
          openrouter.ai/keys
        </a>
      </p>
      <label className="grid gap-1">
        <span className="text-muted">{t("key.key")}</span>
        <input
          type="password"
          autoComplete="off"
          spellCheck={false}
          placeholder="sk-or-v1-…"
          className={field}
          value={settings.key}
          onChange={(e) => setSettings({ ...settings, key: e.target.value })}
        />
      </label>
      <label className="grid gap-1">
        <span className="text-muted">{t("key.model")}</span>
        <input
          spellCheck={false}
          placeholder={DEFAULT_MODEL}
          className={field}
          value={settings.model}
          onChange={(e) => setSettings({ ...settings, model: e.target.value })}
        />
      </label>
      <p className="m-0 text-[12px] leading-snug text-faint">{t("key.where")}</p>
      <button
        type="submit"
        disabled={!settings.key.trim()}
        className="justify-self-start h-8 px-3 rounded-lg bg-primary text-on-primary font-medium hover:bg-primary-hover disabled:opacity-40"
      >
        {t("key.save")}
      </button>
    </form>
  );
}
