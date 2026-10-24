// A note's files, in its sidebar under the sections: each by its name — the name Python opens it by
// (features/files) — and its size; clicked, saved to the reader's disk. Its author adds files (or drops them
// on the note: useAttach) and removes them.
import { useAtomSet } from "@effect-atom/atom-react";
import { FIRMWARE_MAX } from "@electro/notes-api";
import { useCallback, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { bytesOf, nameFor, sizeOf } from "@/features/files/files";
import { failure } from "@/features/notes/sync";
import { uploadFirmware } from "@/features/simulation/atoms";
import type { NoteFile } from "@/shared/model/types";
import { Plus, Trash } from "@/shared/ui/icons";

/** ``attach(list)``: the files kept (as a board's program is) and named on the note; what went wrong, said. */
export function useAttach(setFiles: (fn: (files: NoteFile[]) => NoteFile[]) => void) {
  const { t } = useTranslation("notebook", { keyPrefix: "files" });
  const upload = useAtomSet(uploadFirmware, { mode: "promiseExit" });
  const [problem, setProblem] = useState<string | null>(null);
  const attach = useCallback(
    async (list: Iterable<File>) => {
      setProblem(null);
      for (const file of list) {
        const bytes = new Uint8Array(await file.arrayBuffer());
        if (!bytes.length || bytes.length > FIRMWARE_MAX) {
          setProblem(t("tooBig", { name: file.name, max: sizeOf(FIRMWARE_MAX) }));
          continue;
        }
        const exit = await upload({ payload: bytes });
        if (exit._tag === "Failure") {
          const tag = failure(exit.cause)?._tag;
          setProblem(
            t(tag === "Unauthorized" ? "signedOut" : tag === "FirmwareQuota" ? "quota" : "failed", { name: file.name }),
          );
          continue;
        }
        const { id, size } = exit.value;
        setFiles((files) => [...files, { name: nameFor(file.name, files), id, size }]);
      }
    },
    [upload, setFiles, t],
  );
  return { attach, problem };
}

/** Saved to the reader's disk, under its name. */
async function save(f: NoteFile) {
  const bytes = await bytesOf(f);
  const url = URL.createObjectURL(new Blob([bytes as Uint8Array<ArrayBuffer>]));
  const a = document.createElement("a");
  a.href = url;
  a.download = f.name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function Files({
  files,
  editing,
  problem,
  onAdd,
  onRemove,
}: {
  files: readonly NoteFile[];
  editing: boolean;
  problem: string | null;
  onAdd: (list: File[]) => void;
  onRemove: (name: string) => void;
}) {
  const { t } = useTranslation("notebook", { keyPrefix: "files" });
  const picker = useRef<HTMLInputElement>(null);
  if (!files.length && !editing) return null;
  return (
    <section className="flex-none mt-3 pt-2 border-t border-line">
      <h2 className="mx-2.5 my-1 text-[13px] font-medium text-muted">{t("title")}</h2>
      <ul className="m-0 p-0 list-none grid gap-px">
        {files.map((f) => (
          <li key={f.name} className="group flex items-center gap-1 pr-1 rounded-lg hover:bg-hover">
            <button
              className="flex-1 min-w-0 flex items-baseline gap-2 py-1.5 pl-2.5 text-left text-[14px]"
              title={t("save")}
              onClick={() => void save(f)}
            >
              <span className="truncate font-mono text-[13px]">{f.name}</span>
              <span className="flex-none text-[12px] text-faint">{sizeOf(f.size)}</span>
            </button>
            {editing && (
              <button
                className="flex-none p-1 rounded-md text-muted opacity-0 group-hover:opacity-100 focus:opacity-100 hover:text-fg [&_svg]:size-3.5"
                title={t("remove")}
                aria-label={t("remove")}
                onClick={() => onRemove(f.name)}
              >
                <Trash />
              </button>
            )}
          </li>
        ))}
      </ul>
      {problem && <p className="mx-2.5 my-1 text-[12px] text-danger">{problem}</p>}
      {editing && (
        <>
          <button
            className="inline-flex items-center gap-1.5 h-8 mt-1 px-2.5 rounded-lg text-[14px] text-muted hover:bg-hover hover:text-fg [&_svg]:size-4"
            title={t("hint")}
            onClick={() => picker.current?.click()}
          >
            <Plus /> {t("add")}
          </button>
          <input
            ref={picker}
            type="file"
            multiple
            hidden
            onChange={(e) => {
              onAdd(Array.from(e.target.files ?? []));
              e.target.value = "";
            }}
          />
        </>
      )}
    </section>
  );
}
