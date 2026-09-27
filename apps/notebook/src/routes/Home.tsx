// / — all notes (newest first) as first pages; a new one, one from a file, one from an example.
import { Result, useAtomRefresh, useAtomSet, useAtomValue } from "@effect-atom/atom-react";
import { previewOf } from "@electro/notes-api";
import { Exit } from "effect";
import { useEffect, useRef, useState } from "react";
import { EXAMPLES, fromExample } from "../examples";
import { blank, copyOf } from "../format";
import { Bolt, Plus, Upload } from "../icons";
import { library } from "../Notebook";
import { notesAtom, NOTES, removeNote, toDocument } from "../notes/atoms";
import { useCreateNote } from "../notes/create";
import { Card, when } from "../notes/Gallery";
import { CardSkeletons } from "../Skeletons";
import { upload } from "../storage";

export function Home() {
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
      if (!(await create(await make()))) setProblem("Serwer notatek nie odpowiada — spróbuj za chwilę.");
    } catch (error) {
      setProblem(String((error as Error).message ?? error));
    }
  };

  return (
    <div className="notebook">
      <div className="float top-left no-print">
        <span className="brand" title="electro — notatnik elektroniki"><Bolt /></span>
        <span className="app-name">electro</span>
      </div>
      <div className="float-group top-right no-print">
        <button className="float icon-button" onClick={() => fileInput.current?.click()}
                title="Otwórz plik .electro.json jako nową notatkę" aria-label="Otwórz plik"><Upload /></button>
        <input ref={fileInput} type="file" accept=".json" hidden
               onChange={(e) => { const file = e.target.files?.[0]; e.target.value = ""; if (file) void start(async () => copyOf(await upload(file))); }} />
      </div>

      <div className="gallery">
        <h1>Notatki</h1>
        {problem && <p className="gallery-note error">{problem}</p>}
        <div className="gallery-grid">
          <button className="card new" onClick={() => start(async () => blank())}>
            <span className="thumb"><Plus /></span>
            <span className="card-title">Nowa notatka</span>
          </button>
          {Result.builder(notes)
            .onInitial(() => <CardSkeletons />)
            .onFailure(() => null)
            .onSuccess((list) => list.map((note, i) => (
              <Card key={note.id} index={i} id={note.id} to={`/notes/${note.slug}`} title={note.title || "Bez tytułu"}
                    meta={when(note.modified)} preview={note.preview} library={library}
                    actions={[{
                      label: "Usuń notatkę",
                      danger: true,
                      run: async () => {
                        if (!confirm(`Usunąć notatkę „${note.title || "Bez tytułu"}”? Tego nie da się cofnąć.`)) return;
                        const exit = await remove({ path: { id: note.id }, reactivityKeys: NOTES });
                        if (Exit.isFailure(exit)) setProblem("Nie udało się usunąć — serwer notatek nie odpowiada.");
                      },
                    }]} />
            )))
            .render()}
        </div>
        {Result.isFailure(notes) && (
          <p className="gallery-note">Serwer notatek nie odpowiada — notatki pojawią się, gdy wróci.</p>
        )}

        <h2>Przykłady</h2>
        <div className="gallery-grid">
          {EXAMPLES.map(({ name, notebook }) => (
            <Card key={name} title={notebook.title} meta="nowa notatka z przykładu" library={library}
                  preview={previewOf(toDocument(notebook))}
                  onClick={() => start(async () => fromExample(name)!)} />
          ))}
        </div>
      </div>
    </div>
  );
}
