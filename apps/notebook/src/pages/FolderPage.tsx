// /f/:id/:name — a folder: the way up to it, its name (renamed here), what is in it. The name in
// the address follows the folder's. Its owner shares it from here.
import { Result, useAtomSet, useAtomValue } from "@effect-atom/atom-react";
import { RANK, slugify } from "@electro/notes-api";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams } from "react-router";
import { Breadcrumbs, LibraryGrid, useLibraryCalls } from "@/features/library";
import { CardSkeletons, failure, folderAtom, folderUrl, LIBRARY, patchItem } from "@/features/notes";
import { SettingsMenu } from "@/features/settings";
import { ShareDialog, enabled as sharingOn } from "@/features/sharing";
import { useTitle } from "@/shared/hooks/useTitle";
import { cn } from "@/shared/lib/cn";
import { IslandButton, IslandLink, Islands } from "@/shared/ui/Island";
import { Back, ShareIcon } from "@/shared/ui/icons";
import { PageMessage } from "@/shared/ui/PageMessage";

export function FolderPage() {
  const { t } = useTranslation("library");
  const { id = "", name = "" } = useParams();
  const navigate = useNavigate();
  const folder = useAtomValue(folderAtom(id));
  const patch = useAtomSet(patchItem, { mode: "promiseExit" });
  const [problem, setProblem] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [sharing, setSharing] = useState(false);
  const { said, moveTo } = useLibraryCalls(setProblem);

  const here = Result.isSuccess(folder) ? folder.value : null;
  useTitle(here ? here.folder.name || t("untitled") : null);
  useEffect(() => {
    // the name in the address: the folder's own (it may have been renamed)
    if (here && name !== slugify(here.folder.name || "folder"))
      navigate(folderUrl(id, here.folder.name), { replace: true });
  }, [here, id, name, navigate]);

  const up = here?.path.at(-1);
  const back = up ? { to: folderUrl(up.id, up.name), label: up.name } : { to: "/", label: t("home") };
  const backIsland = (
    <Islands side="left">
      <IslandLink to={back.to} title={back.label} aria-label={back.label}>
        <Back />
      </IslandLink>
    </Islands>
  );

  if (Result.isFailure(folder)) {
    const missing = failure(folder.cause)?._tag === "NotFound";
    return (
      <>
        {backIsland}
        <PageMessage title={missing ? t("folder.missing") : t("folder.unreachable")}>
          <p className="text-muted">
            {missing && t("folder.missingText")} <Link to="/">{t("home")}</Link>
          </p>
        </PageMessage>
      </>
    );
  }

  const role = here?.folder.role ?? "viewer";
  const rename = async (next: string) => {
    setEditing(false);
    if (!here || !next.trim() || next.trim() === here.folder.name) return;
    said(await patch({ path: { id }, payload: { name: next.trim() }, reactivityKeys: LIBRARY }));
  };

  return (
    <div>
      {backIsland}
      <Islands side="right">
        {sharingOn && role === "owner" && (
          <IslandButton onClick={() => setSharing(true)} title={t("share")} aria-label={t("share")}>
            <ShareIcon />
          </IslandButton>
        )}
        <SettingsMenu />
      </Islands>
      {sharing && here && <ShareDialog item={here.folder} onClose={() => setSharing(false)} />}
      <div className="mx-auto max-w-310 px-8 max-sm:px-4 pt-21 pb-24">
        {here && (
          <Breadcrumbs
            path={here.path}
            current={here.folder.name || t("untitled")}
            onDrop={(card, into) => void moveTo(card, into)}
          />
        )}
        <div className="flex items-center gap-3 mb-5">
          {editing && here ? (
            <input
              autoFocus
              defaultValue={here.folder.name}
              aria-label={t("rename")}
              spellCheck={false}
              onBlur={(e) => void rename(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") void rename(e.currentTarget.value);
                if (e.key === "Escape") setEditing(false);
              }}
              className="flex-1 max-w-160 m-0 py-0.5 px-2 -ml-2 rounded-lg border border-line bg-paper text-[22px] font-medium outline-none focus:border-accent"
            />
          ) : (
            <h1
              className={cn(
                "m-0 py-0.5 px-2 -ml-2 rounded-lg text-[22px] font-medium",
                RANK[role] >= RANK.editor && "cursor-text hover:bg-hover",
              )}
              title={RANK[role] >= RANK.editor ? t("folder.renameTitle") : undefined}
              onClick={() => RANK[role] >= RANK.editor && setEditing(true)}
            >
              {here ? here.folder.name || t("untitled") : " "}
            </h1>
          )}
          {here && role === "viewer" && (
            <span className="px-2 py-0.5 rounded-md bg-hover text-[13px] text-muted" title={t("folder.readOnlyTitle")}>
              {t("folder.readOnly")}
            </span>
          )}
        </div>
        {problem && <p className="mb-3.5 text-[14px] text-danger">{problem}</p>}
        {here ? (
          <LibraryGrid
            items={here.items}
            parentId={id}
            container={role}
            label={t("folder.contents")}
            onProblem={setProblem}
          />
        ) : (
          <ul className="grid grid-cols-[repeat(auto-fill,212px)] gap-x-6 gap-y-7 max-sm:grid-cols-[repeat(2,212px)] max-sm:justify-between max-sm:gap-x-4 max-sm:[zoom:0.74]">
            <CardSkeletons />
          </ul>
        )}
        {here && !here.items.length && role === "viewer" && <p className="text-muted">{t("folder.empty")}</p>}
      </div>
    </div>
  );
}
