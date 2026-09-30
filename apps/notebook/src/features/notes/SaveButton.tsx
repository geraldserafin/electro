// The save button: a click opens the card of what is going on (SaveCard) — there, saving now (the
// session as one commit, with GitHub on its main; also ⌘S / Ctrl+S, from anywhere) and connecting
// GitHub (features/vault: until a save it autosaves by itself). A dot on it: changes not autosaved yet; red:
// saving did not work. What came from GitHub (or another tab) shows at once: the lists read again
// ("electro:pulled"; a note open here reads itself again).
import { useAtomSet } from "@effect-atom/atom-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { configured, connection, save, useSaveState } from "@/features/vault";
import { useClickOutside } from "@/shared/hooks/useClickOutside";
import { IslandButton } from "@/shared/ui/Island";
import { SaveIcon, WarningIcon } from "@/shared/ui/icons";
import { LIBRARY, refreshLibrary } from "./atoms";
import { readSaveDetails, SaveCard } from "./SaveCard";

const mac = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform);

export function SaveButton() {
  const { t } = useTranslation("notes", { keyPrefix: "save" });
  const state = useSaveState();
  const refresh = useAtomSet(refreshLibrary, { mode: "promise" });
  const [connectFailed, setConnectFailed] = useState(() => new URLSearchParams(location.search).has("github"));

  // the card's details, read ahead whenever saving moves on: it opens with them at once
  useEffect(readSaveDetails, [state.pending, state.open, state.saving]);

  useEffect(() => {
    const pulled = () => void refresh({ reactivityKeys: LIBRARY });
    window.addEventListener("electro:pulled", pulled);
    return () => window.removeEventListener("electro:pulled", pulled);
  }, [refresh]);

  useEffect(() => {
    const press = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && !e.altKey && e.key.toLowerCase() === "s") {
        e.preventDefault();
        setConnectFailed(false);
        void save();
      }
    };
    window.addEventListener("keydown", press);
    return () => window.removeEventListener("keydown", press);
  }, []);

  const title = [
    `${t("label")} (${mac ? "⌘S" : "Ctrl+S"})`,
    state.saving ? t("saving") : state.pending ? t("pending") : state.open ? t("autosaved") : t("saved"),
    connection() === null && configured() ? t("local") : null,
  ]
    .filter(Boolean)
    .join(" — ");
  const problem = state.error ? t(state.error) : connectFailed ? t("connectFailed") : null;
  // the card under it: open on a click, closed by another, a click beside it, or Esc
  const [card, setCard] = useState(false);
  const here = useRef<HTMLSpanElement>(null);
  const close = useCallback(() => setCard(false), []);
  useClickOutside(here, card, close);
  useEffect(() => {
    if (!card) return;
    const esc = (e: KeyboardEvent) => e.key === "Escape" && close();
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [card, close]);

  return (
    <>
      <span className="relative" ref={here}>
        <IslandButton
          onClick={() => setCard(!card)}
          on={card}
          waiting={state.saving}
          aria-label={title}
          aria-haspopup="dialog"
          aria-expanded={card}
          className="relative"
        >
          <SaveIcon />
          {(state.pending || state.error) && (
            <span
              aria-hidden="true"
              className={`absolute top-2 right-2 size-2 rounded-full ${state.error ? "bg-danger" : "bg-accent"}`}
            />
          )}
        </IslandButton>
        {card && (
          <SaveCard
            state={state}
            onSave={() => {
              setConnectFailed(false);
              void save();
            }}
          />
        )}
      </span>
      {problem && (
        <div
          role="alert"
          data-notice
          className="fixed bottom-4 inset-x-0 mx-auto w-fit max-w-[calc(100vw-32px)] z-25 flex items-center gap-2.5 py-2 px-3.5 rounded-xl border border-line bg-surface text-fg text-[14px] animate-rise [&>svg]:flex-none [&>svg]:text-warn"
        >
          <WarningIcon />
          <span>
            {problem}
            {state.error && state.detail && <span className="block text-[12px] text-muted">{state.detail}</span>}
          </span>
        </div>
      )}
    </>
  );
}
