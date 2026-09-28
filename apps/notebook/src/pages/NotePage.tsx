// /n/:id/:name — a note, read from the server and edited (or only read, if it was shared with the
// user to read). The way back is the folder it is in; the name in the address follows its title.
import { useAtomSet } from "@effect-atom/atom-react";
import { RANK, slugify } from "@electro/notes-api";
import { Exit } from "effect";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams } from "react-router";
import { Notebook, NoteSkeleton } from "@/features/notebook";
import { failure, folderUrl, fromDocument, getNote, noteUrl } from "@/features/notes";
import type { Notebook as NotebookData } from "@/shared/model/types";
import { Back } from "@/shared/ui/icons";
import { IslandLink, Islands } from "@/shared/ui/Island";
import { PageMessage } from "@/shared/ui/PageMessage";

type Loaded =
  | { kind: "loading" }
  | { kind: "ready"; notebook: NotebookData; revision: number; readOnly: boolean; back: { to: string; label: string } }
  | { kind: "missing" }
  | { kind: "unreachable" };

export function NotePage() {
  const { t } = useTranslation("pages", { keyPrefix: "note" });
  const { t: tLibrary } = useTranslation("library");
  const { id = "", name = "" } = useParams();
  const navigate = useNavigate();
  const get = useAtomSet(getNote, { mode: "promiseExit" });
  const [loaded, setLoaded] = useState<Loaded>({ kind: "loading" });
  const [reads, setReads] = useState(0); // "read it again" (after a conflict, or a failed read)
  const home = { to: "/", label: tLibrary("home") };

  useEffect(() => {
    let alive = true;
    setLoaded({ kind: "loading" });
    void get({ path: { id } }).then((exit) => {
      if (!alive) return;
      if (Exit.isFailure(exit)) {
        setLoaded(failure(exit.cause)?._tag === "NotFound" ? { kind: "missing" } : { kind: "unreachable" });
        return;
      }
      const { document, revision, role, path } = exit.value;
      const up = path.at(-1);
      setLoaded({
        kind: "ready", notebook: fromDocument(document), revision, readOnly: RANK[role] < RANK.editor,
        back: up ? { to: folderUrl(up.id, up.name), label: up.name } : home,
      });
    });
    return () => {
      alive = false;
    };
  }, [id, reads, get]); // eslint-disable-line react-hooks/exhaustive-deps

  if (loaded.kind === "ready") {
    return (
      <Notebook
        key={`${loaded.notebook.id}:${reads}`} // a note read again starts afresh
        initial={loaded.notebook}
        revision={loaded.revision}
        reload={() => setReads((n) => n + 1)}
        readOnly={loaded.readOnly}
        back={loaded.back}
        onTitle={(title) => { // the name in the address follows the title
          if (name !== slugify(title || "notatka")) navigate(noteUrl(id, title), { replace: true });
        }}
      />
    );
  }
  const back = (
    <Islands side="left"><IslandLink to={home.to} title={home.label} aria-label={home.label}><Back /></IslandLink></Islands>
  );
  if (loaded.kind === "loading") return <>{back}<NoteSkeleton /></>;
  return (
    <>
      {back}
      {loaded.kind === "missing" && (
        <PageMessage title={t("missing")}>
          <p className="text-muted">{t("maybeDeleted")} <Link to="/">{home.label}</Link></p>
        </PageMessage>
      )}
      {loaded.kind === "unreachable" && (
        <PageMessage title={t("unreachable")}>
          <p className="text-muted">{t("unreachableText")}</p>
          <button className="inline-flex items-center px-2.5 py-1 rounded-md border border-transparent bg-accent text-[15px] text-white hover:brightness-108" onClick={() => setReads((n) => n + 1)}>{t("retry")}</button>
        </PageMessage>
      )}
    </>
  );
}
