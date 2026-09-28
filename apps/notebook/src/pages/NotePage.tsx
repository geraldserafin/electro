// /notes/:ref — the note at this address (its slug, an older slug, or its id), read from the
// server and edited. The address shown is always the current slug.
import { useAtomSet } from "@effect-atom/atom-react";
import { Exit } from "effect";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams } from "react-router";
import { Notebook, NoteSkeleton } from "@/features/notebook";
import { failure, fromDocument, getNote } from "@/features/notes";
import type { Notebook as NotebookData } from "@/shared/model/types";
import { Back } from "@/shared/ui/icons";
import { IslandLink, Islands } from "@/shared/ui/Island";
import { PageMessage } from "@/shared/ui/PageMessage";

type Loaded =
  | { kind: "loading" }
  | { kind: "ready"; notebook: NotebookData; revision: number; slug: string }
  | { kind: "missing" }
  | { kind: "unreachable" };

export function NotePage() {
  const { t } = useTranslation("pages", { keyPrefix: "note" });
  const { t: tNote } = useTranslation("notebook");
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
  const back = (
    <Islands side="left">
      <IslandLink to="/" title={tNote("allNotes")} aria-label={tNote("allNotes")}><Back /></IslandLink>
    </Islands>
  );
  if (loaded.kind === "loading") return <>{back}<NoteSkeleton /></>;
  return (
    <>
      {back}
      {loaded.kind === "missing" && (
        <PageMessage title={t("missing")}>
          <p className="text-muted">{t("maybeDeleted")} <Link to="/">{tNote("allNotes")}</Link></p>
        </PageMessage>
      )}
      {loaded.kind === "unreachable" && (
        <PageMessage title={t("unreachable")}>
          <p className="text-muted">{t("unreachableText")}</p>
          <button className="primary" onClick={() => setReads((n) => n + 1)}>{t("retry")}</button>
        </PageMessage>
      )}
    </>
  );
}
