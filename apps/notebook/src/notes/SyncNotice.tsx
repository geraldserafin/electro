// Saving happens in the background and says nothing while it works. Only when it cannot — the
// note changed elsewhere, or the server is away — a small notice shows, at the bottom.
import { WarningIcon } from "../icons";
import type { SyncState } from "./sync";

export function SyncNotice({ state, onKeepMine, onTakeTheirs }: {
  state: SyncState; onKeepMine: () => void; onTakeTheirs: () => void;
}) {
  if (state.kind === "conflict")
    return (
      <div className="notice conflict" role="alert">
        <WarningIcon />
        <span>Ta notatka zmieniła się gdzie indziej. Którą wersję zostawić?</span>
        <button onClick={onKeepMine}>Moją</button>
        <button onClick={onTakeTheirs}>Z serwera</button>
      </div>
    );
  if (state.kind === "offline" || state.kind === "error")
    return (
      <div className="notice" role="status">
        <WarningIcon />
        <span>
          {state.kind === "offline"
            ? "Serwer notatek nie odpowiada — zmiany wyślę, gdy wróci."
            : `Nie udało się zapisać: ${state.message}`}
        </span>
      </div>
    );
  return null;
}
