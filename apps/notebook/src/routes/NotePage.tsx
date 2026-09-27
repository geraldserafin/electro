// /notes/:ref — the note at this address (its slug, an older slug, or its id), read from the
// server and edited. The address shown is always the current slug.
import { useAtomSet } from "@effect-atom/atom-react";
import { Exit } from "effect";
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { Back } from "../icons";
import { fromDocument, getNote } from "../notes/atoms";
import { failure } from "../notes/sync";
import { Notebook } from "../Notebook";
import type { Notebook as NotebookData } from "../types";

type Loaded =
  | { kind: "loading" }
  | { kind: "ready"; notebook: NotebookData; revision: number; slug: string }
  | { kind: "missing" }
  | { kind: "unreachable" };

export function NotePage() {
  const { ref = "" } = useParams();
  const navigate = useNavigate();
  const get = useAtomSet(getNote, { mode: "promiseExit" });
  const [loaded, setLoaded] = useState<Loaded>({ kind: "loading" });
  const [reads, setReads] = useState(0); // "read it again" (after a conflict, or a failed read)
  // the addresses of the note on screen (its id, its slugs): a move between them is not a new note
  const addresses = useRef(new Set<string>());
  const readAt = useRef(-1);

  useEffect(() => {
    if (addresses.current.has(ref) && readAt.current === reads) return; // the same note, renamed
    let alive = true;
    setLoaded({ kind: "loading" });
    void get({ path: { ref } }).then((exit) => {
      if (!alive) return;
      if (Exit.isFailure(exit)) {
        addresses.current = new Set();
        setLoaded(failure(exit.cause)?._tag === "NoteNotFound" ? { kind: "missing" } : { kind: "unreachable" });
        return;
      }
      const { document, revision, slug } = exit.value;
      addresses.current = new Set([document.id, slug, ref]);
      readAt.current = reads;
      setLoaded({ kind: "ready", notebook: fromDocument(document), revision, slug });
      if (ref !== slug) navigate(`/notes/${slug}`, { replace: true }); // an id or an old slug: show the current one
    });
    return () => {
      alive = false;
    };
  }, [ref, reads, get, navigate]);

  if (loaded.kind === "ready") {
    return (
      <Notebook
        key={`${loaded.notebook.id}:${reads}`} // a note read again starts afresh
        initial={loaded.notebook}
        revision={loaded.revision}
        reload={() => setReads((n) => n + 1)}
        onSaved={(slug) => { // a new title, a new address (the old one keeps working)
          addresses.current.add(slug);
          if (slug !== ref) navigate(`/notes/${slug}`, { replace: true });
        }}
      />
    );
  }
  return (
    <div className="notebook">
      <div className="float top-left no-print">
        <Link className="icon-button" to="/" title="Wszystkie notatki" aria-label="Wszystkie notatki"><Back /></Link>
      </div>
      <div className="page-message">
        {loaded.kind === "loading" && <p className="muted">Wczytuję notatkę…</p>}
        {loaded.kind === "missing" && (
          <>
            <h1>Nie ma takiej notatki</h1>
            <p className="muted">Może została usunięta. <Link to="/">Wszystkie notatki</Link></p>
          </>
        )}
        {loaded.kind === "unreachable" && (
          <>
            <h1>Serwer notatek nie odpowiada</h1>
            <p className="muted">Notatka jest na serwerze, a ten jest teraz niedostępny.</p>
            <button className="primary" onClick={() => setReads((n) => n + 1)}>Spróbuj ponownie</button>
          </>
        )}
      </div>
    </div>
  );
}
