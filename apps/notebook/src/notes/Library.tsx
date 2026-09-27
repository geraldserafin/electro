// The notes on the server: a side panel with the list (open, new, delete), and the small sign in
// the app bar that says whether the open notebook is saved there.
import { Result, useAtomValue } from "@effect-atom/atom-react";
import type { NoteSummary } from "@electro/notes-api";
import { useEffect, useRef, useState } from "react";
import { Cloud, CloudOff, Plus, Trash, WarningIcon as Warning } from "../icons";
import { notesAtom } from "./atoms";
import type { SyncState } from "./sync";

const when = (iso: string) => {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  const today = new Date().toDateString() === date.toDateString();
  return today
    ? date.toLocaleTimeString("pl-PL", { hour: "2-digit", minute: "2-digit" })
    : date.toLocaleDateString("pl-PL", { day: "numeric", month: "short", year: "numeric" });
};

const plural = (n: number, one: string, few: string, many: string) =>
  `${n} ${n === 1 ? one : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20) ? few : many}`;

export function Library({ currentId, onOpen, onCreate, onDelete }: {
  currentId: string;
  onOpen: (id: string) => void;
  onCreate: () => void;
  onDelete: (note: NoteSummary) => void;
}) {
  const notes = useAtomValue(notesAtom);
  return (
    <aside className="library-panel no-print" aria-label="Notatki">
      <header>
        <h2>Notatki</h2>
        <button className="new-note" onClick={onCreate} title="Nowa, pusta notatka"><Plus /> Nowa</button>
      </header>
      {Result.builder(notes)
        .onInitial(() => <p className="muted pad">Ładuję…</p>)
        .onFailure(() => (
          <p className="muted pad">
            Serwer notatek jest niedostępny — notatnik zapisuje się tylko w tej przeglądarce.
          </p>
        ))
        .onSuccess((list) => list.length === 0
          ? <p className="muted pad">Jeszcze nic — ten notatnik zapisze się tu sam.</p>
          : (
            <ul>
              {list.map((note) => (
                <li key={note.id} className={note.id === currentId ? "current" : ""} data-id={note.id}>
                  <button className="open" onClick={() => onOpen(note.id)} aria-current={note.id === currentId}>
                    <span className="note-title">{note.title || "Bez tytułu"}</span>
                    <span className="meta">
                      {when(note.modified)} · {plural(note.cells, "komórka", "komórki", "komórek")}
                      {note.schematics > 0 && ` · ${plural(note.schematics, "schemat", "schematy", "schematów")}`}
                    </span>
                  </button>
                  <button className="delete" onClick={() => onDelete(note)} title="Usuń notatkę" aria-label="Usuń notatkę">
                    <Trash />
                  </button>
                </li>
              ))}
            </ul>
          ))
        .render()}
    </aside>
  );
}

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
