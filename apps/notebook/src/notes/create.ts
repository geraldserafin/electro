// Starting a note — empty, from an example, from a file: it is made on the server first, then
// opened at its address.
import { useAtomSet } from "@effect-atom/atom-react";
import { Exit } from "effect";
import { useNavigate } from "react-router";
import type { Notebook } from "../types";
import { NOTES, saveNote, toDocument } from "./atoms";

export function useCreateNote() {
  const save = useAtomSet(saveNote, { mode: "promiseExit" });
  const navigate = useNavigate();
  /** Stores ``notebook`` as a new note and goes there; false if the server could not take it. */
  return async (notebook: Notebook, { replace = false } = {}): Promise<boolean> => {
    const exit = await save({
      path: { id: notebook.id },
      payload: { document: toDocument(notebook), baseRevision: null },
      reactivityKeys: NOTES,
    });
    if (Exit.isFailure(exit)) return false;
    navigate(`/notes/${exit.value.slug}`, { replace });
    return true;
  };
}
