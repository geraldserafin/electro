// / — all notes (newest first) as first pages; a new one, one from a file, one from an example.
import { Result, useAtomRefresh, useAtomSet, useAtomValue } from "@effect-atom/atom-react";
import { previewOf } from "@electro/notes-api";
import { Exit } from "effect";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { EXAMPLES, fromExample } from "@/features/examples";
import { Card, CardSkeletons, NewCard, NOTES, notesAtom, removeNote, toDocument, useCreateNote, useWhen } from "@/features/notes";
import { library } from "@/features/schematic";
import { LanguageButton } from "@/features/language";
import { ThemeButton } from "@/features/theme";
import { blank, copyOf, upload } from "@/shared/model/format";
import { Upload } from "@/shared/ui/icons";
import { Brand, IslandButton, Islands } from "@/shared/ui/Island";

const grid = "m-0 p-0 list-none grid grid-cols-[repeat(auto-fill,212px)] gap-x-6 gap-y-7";
const note = "mt-6 text-[14px]";

export function Home() {
  const { t } = useTranslation("pages", { keyPrefix: "home" });
  const { t: tNotes } = useTranslation("notes");
  const when = useWhen();
  const notes = useAtomValue(notesAtom);
  const refresh = useAtomRefresh(notesAtom);
  useEffect(refresh, [refresh]); // notes change on their own pages: read the list afresh on coming back
  const create = useCreateNote();
  const remove = useAtomSet(removeNote, { mode: "promiseExit" });
  const fileInput = useRef<HTMLInputElement>(null);
  const [problem, setProblem] = useState<string | null>(null);

  const start = async (make: () => Promise<Parameters<typeof create>[0]>) => {
    try {
      setProblem(null);
      if (!(await create(await make()))) setProblem(t("createFailed"));
    } catch (error) {
      setProblem(String((error as Error).message ?? error));
    }
  };

  return (
    <div>
      <Islands side="left"><Brand title={t("brand")} /></Islands>
      <Islands side="right">
        <IslandButton onClick={() => fileInput.current?.click()} title={t("openFileTitle")} aria-label={t("openFile")}><Upload /></IslandButton>
        <input ref={fileInput} type="file" accept=".json" hidden
               onChange={(e) => { const file = e.target.files?.[0]; e.target.value = ""; if (file) void start(async () => copyOf(await upload(file))); }} />
        <LanguageButton />
        <ThemeButton />
      </Islands>

      <div className="mx-auto max-w-310 px-8 pt-21 pb-24">
        <h1 className="mt-0 mb-5 text-[22px] font-medium">{t("notes")}</h1>
        {problem && <p className={`${note} text-danger`}>{problem}</p>}
        <ul className={grid} aria-label={t("notes")}>
          <NewCard onClick={() => start(async () => blank())} />
          {Result.builder(notes)
            .onInitial(() => <CardSkeletons />)
            .onFailure(() => null)
            .onSuccess((list) => list.map((n, i) => {
              const title = n.title || tNotes("untitled");
              return (
                <Card key={n.id} index={i} id={n.id} to={`/notes/${n.slug}`} title={title}
                      meta={when(n.modified)} preview={n.preview} library={library}
                      actions={[{
                        label: t("deleteNote"),
                        danger: true,
                        run: async () => {
                          if (!confirm(t("confirmDelete", { title }))) return;
                          const exit = await remove({ path: { id: n.id }, reactivityKeys: NOTES });
                          if (Exit.isFailure(exit)) setProblem(t("deleteFailed"));
                        },
                      }]} />
              );
            }))
            .render()}
        </ul>
        {Result.isFailure(notes) && <p className={`${note} text-muted`}>{t("listUnavailable")}</p>}

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
