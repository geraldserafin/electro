// / — the user's library: their own folders and notes, and what others shared with them; a new
// note or folder; a note from a file or an example (at the top).
import { Result, useAtomRefresh, useAtomValue } from "@effect-atom/atom-react";
import { previewOf } from "@electro/notes-api";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { EXAMPLES, fromExample } from "@/features/examples";
import { LibraryGrid } from "@/features/library";
import { Card, CardSkeletons, homeAtom, toDocument, useCreateNote } from "@/features/notes";
import { library } from "@/features/schematic";
import { SettingsMenu } from "@/features/settings";
import { copyOf, FormatError, upload } from "@/shared/model/format";
import { Upload } from "@/shared/ui/icons";
import { Brand, IslandButton, Islands } from "@/shared/ui/Island";
import { cn } from "@/shared/lib/cn";

const grid = "grid grid-cols-[repeat(auto-fill,212px)] gap-x-6 gap-y-7";
const note = "mt-6 mb-3.5 text-[14px] text-muted";

export function Home() {
  const { t } = useTranslation("pages", { keyPrefix: "home" });
  const { t: tLibrary } = useTranslation("library");
  const { t: tFile } = useTranslation("pages", { keyPrefix: "file" });
  const items = useAtomValue(homeAtom);
  const refresh = useAtomRefresh(homeAtom);
  useEffect(refresh, [refresh]); // things change on their own pages: read the home screen afresh on coming back
  const create = useCreateNote();
  const fileInput = useRef<HTMLInputElement>(null);
  const [problem, setProblem] = useState<string | null>(null);

  const start = async (make: () => Promise<Parameters<typeof create>[0]>) => {
    try {
      setProblem(null);
      if (!(await create(await make()))) setProblem(t("createFailed"));
    } catch (error) {
      setProblem(error instanceof FormatError ? tFile(error.issue.type, error.issue) : String((error as Error).message ?? error));
    }
  };

  return (
    <div>
      <Islands side="left"><Brand title={t("brand")} /></Islands>
      <Islands side="right">
        <IslandButton onClick={() => fileInput.current?.click()} title={t("openFileTitle")} aria-label={t("openFile")}><Upload /></IslandButton>
        <input ref={fileInput} type="file" accept=".json" hidden
               onChange={(e) => { const file = e.target.files?.[0]; e.target.value = ""; if (file) void start(async () => copyOf(await upload(file))); }} />
        <SettingsMenu />
      </Islands>

      <div className="mx-auto max-w-310 px-8 pt-21 pb-24">
        <h1 className="mt-0 mb-5 text-[22px] font-medium">{tLibrary("home")}</h1>
        {problem && <p className={cn(note, "text-danger")}>{problem}</p>}
        {Result.isSuccess(items)
          ? <LibraryGrid items={items.value} parentId={null} container={null} label={tLibrary("home")} onProblem={setProblem} />
          : <ul className={grid}>{Result.isFailure(items) ? null : <CardSkeletons />}</ul>}
        {Result.isFailure(items) && <p className={note}>{t("listUnavailable")}</p>}

        <h2 className="mt-12 mb-4 text-[16px] font-medium text-muted">{t("examples")}</h2>
        <ul className={grid} aria-label={t("examples")}>
          {EXAMPLES.map(({ name, notebook }) => (
            <Card key={name} title={notebook.title} meta={t("fromExample")} library={library}
                  preview={previewOf(toDocument(notebook))}
                  onClick={() => start(async () => fromExample(name)!)} />
          ))}
        </ul>
      </div>
    </div>
  );
}
