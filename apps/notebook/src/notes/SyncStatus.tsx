// The sign in the app bar that says whether the open notebook is saved on the notes server —
// and, on a conflict, the choice of version.
import { useEffect, useRef, useState } from "react";
import { Cloud, CloudOff, WarningIcon as Warning } from "../icons";
import { when } from "./Gallery";
import type { SyncState } from "./sync";

/** Saved / saving / offline / conflict — and, on a conflict, the choice. */
export function SyncStatus({ state, onKeepMine, onTakeTheirs }: {
  state: SyncState; onKeepMine: () => void; onTakeTheirs: () => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (event: PointerEvent) => { if (!ref.current?.contains(event.target as Node)) setOpen(false); };
    document.addEventListener("pointerdown", close);
    return () => document.removeEventListener("pointerdown", close);
  }, [open]);
  const [icon, title] =
    state.kind === "saved" ? [<Cloud key="c" />, `Zapisano na serwerze (${when(state.at)})`]
    : state.kind === "saving" ? [<Cloud key="c" />, "Zapisuję na serwerze…"]
    : state.kind === "offline" ? [<CloudOff key="o" />, "Serwer niedostępny — zapisane w tej przeglądarce, ponowię próbę"]
    : state.kind === "conflict" ? [<Warning key="w" />, "Ta notatka zmieniła się gdzie indziej — wybierz wersję"]
    : state.kind === "error" ? [<Warning key="w" />, `Nie udało się zapisać: ${state.message}`]
    : [<Cloud key="c" />, "Jeszcze nie zapisano na serwerze"];
  return (
    <div className={`sync ${state.kind}`} ref={ref}>
      <button className="icon-button" title={title} aria-label={title}
              onClick={() => state.kind === "conflict" && setOpen(!open)}>
        {icon}
      </button>
      {open && state.kind === "conflict" && (
        <div className="menu-items conflict" role="dialog" aria-label="Konflikt wersji">
          <p>Ta notatka została zapisana gdzie indziej (wersja {state.current}). Którą zostawić?</p>
          <button onClick={() => { setOpen(false); onKeepMine(); }}>Moją — to, co widać tutaj</button>
          <button onClick={() => { setOpen(false); onTakeTheirs(); }}>Z serwera — porzuć zmiany stąd</button>
        </div>
      )}
    </div>
  );
}
