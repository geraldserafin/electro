// Starting a note — empty, from an example, from a file: it is made on the server first, then
// opened at its address. Without a folder said, at the top of the user's own.
import { useAtomSet } from "@effect-atom/atom-react";
import { Exit } from "effect";
import { useNavigate } from "react-router";
import type { Notebook } from "@/shared/model/types";
import { LIBRARY, noteUrl, saveNote, toDocument } from "./atoms";

export function useCreateNote() {
  const save = useAtomSet(saveNote, { mode: "promiseExit" });
  const navigate = useNavigate();
  /** Stores ``notebook`` as a new note (in the folder ``parentId``) and goes there; false if the
   *  server could not take it. */
  return async (notebook: Notebook, { parentId = null, replace = false }: { parentId?: string | null; replace?: boolean } = {}) => {
    const exit = await save({
      path: { id: notebook.id },
      payload: { document: toDocument(notebook), baseRevision: null, parentId },
      reactivityKeys: LIBRARY,
    });
    if (Exit.isFailure(exit)) return false;
    navigate(noteUrl(notebook.id, notebook.title), { replace });
    return true;
  };
}
