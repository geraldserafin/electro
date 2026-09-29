// Saving happens in the background and says nothing while it works. Only when it cannot — the
// note changed elsewhere, or the server is away — a small notice shows, at the bottom.
import { useTranslation } from "react-i18next";
import { Eye, WarningIcon } from "@/shared/ui/icons";
import type { SyncState } from "./sync";

// data-notice: the notebook keeps its cell focused on a click here
const notice = "fixed bottom-4 inset-x-0 mx-auto w-fit max-w-[calc(100vw-32px)] z-25 flex items-center gap-2.5 py-2 pr-2 pl-3.5 " +
  "rounded-xl border border-line bg-surface text-fg text-[14px] animate-rise [&>svg]:flex-none [&>svg]:text-warn";
const button = "px-3 py-1.25 rounded-lg border border-line text-[14px] hover:bg-selected";

export function SyncNotice({ state, onKeepMine, onTakeTheirs }: {
  state: SyncState; onKeepMine: () => void; onTakeTheirs: () => void;
}) {
  const { t } = useTranslation("notes");
  if (state.kind === "conflict")
    return (
      <div className={notice} data-notice role="alert">
        <WarningIcon />
        <span>{t("sync.conflict")}</span>
        <button className={button} onClick={onKeepMine}>{t("sync.keepMine")}</button>
        <button className={button} onClick={onTakeTheirs}>{t("sync.takeTheirs")}</button>
      </div>
    );
  if (state.kind === "offline" || state.kind === "error")
    return (
      <div className={notice} data-notice role="status">
        <WarningIcon />
        <span>{state.kind === "offline" ? t("sync.offline") : state.tag === "NoteIdMismatch" ? t("sync.mismatch") : t("sync.failed", { tag: state.tag })}</span>
      </div>
    );
  return null;
}

/** Shared with the user to read: it runs and changes here, but nothing is saved — unless they
 *  make a copy of their own. */
export function ReadOnlyNotice({ onCopy }: { onCopy: () => void }) {
  const { t } = useTranslation("notes");
  return (
    <div className={notice} data-notice role="status">
      <Eye />
      <span>{t("readOnly.text")}</span>
      <button className={button} onClick={onCopy}>{t("readOnly.copy")}</button>
    </div>
  );
}
