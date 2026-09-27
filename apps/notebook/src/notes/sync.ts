// Keeping the open notebook on the notes server.
//
// Every change is sent at most a second after it happens, with the revision it was based on;
// one save is in flight at a time (a second one waits), so revisions never cross. A conflict —
// the note changed elsewhere — stops saving until the user picks a version. When the server is
// unreachable the notebook still lives in this browser (storage.ts) and saving is retried.
import { Atom, useAtomSet, useAtomValue } from "@effect-atom/atom-react";
import { Cause, Exit, Option } from "effect";
import { useCallback, useEffect, useRef } from "react";
import { blank } from "../format";
import type { Notebook } from "../types";
import { fromDocument, getNote, NOTES, removeNote, saveNote, toDocument } from "./atoms";

export type SyncState =
  | { kind: "idle" } // nothing sent yet
  | { kind: "saving" }
  | { kind: "saved"; at: string }
  | { kind: "offline" } // the server is unreachable: kept in this browser, retried
  | { kind: "conflict"; current: number } // changed elsewhere since it was read
  | { kind: "error"; message: string };

export const syncStateAtom = Atom.make<SyncState>({ kind: "idle" }).pipe(Atom.keepAlive);

const DELAY = 1000;
const RETRY = 10_000;

// ------------------------------------------------------------------ revisions this browser knows

const REVISIONS_KEY = "electro-notes-revisions";

const revisions = {
  read(): Record<string, number> {
    try {
      return JSON.parse(localStorage.getItem(REVISIONS_KEY) ?? "{}");
    } catch {
      return {};
    }
  },
  get(id: string): number | null {
    return this.read()[id] ?? null;
  },
  set(id: string, revision: number | null) {
    const all = this.read();
    if (revision === null) delete all[id];
    else all[id] = revision;
    try {
      localStorage.setItem(REVISIONS_KEY, JSON.stringify(all));
    } catch {
      // not remembered: the next save from here asks as if new, and gets a conflict to resolve
    }
  },
};

/** The error a failed call ended with, if it is one of ours (tagged), else the defect/transport. */
function failure(cause: Cause.Cause<unknown>): { _tag?: string; current?: number; message?: string } | null {
  const error = Option.getOrNull(Cause.failureOption(cause));
  return (error as { _tag?: string } | null) ?? null;
}

// ------------------------------------------------------------------ the hook

export function useNotesSync(notebook: Notebook, replace: (notebook: Notebook) => void) {
  const state = useAtomValue(syncStateAtom);
  const setState = useAtomSet(syncStateAtom);
  const save = useAtomSet(saveNote, { mode: "promiseExit" });
  const get = useAtomSet(getNote, { mode: "promiseExit" });
  const remove = useAtomSet(removeNote, { mode: "promiseExit" });

  const latest = useRef(notebook);
  latest.current = notebook;
  const current = useRef(state);
  current.current = state;
  const saved = useRef<Notebook | null>(null); // the notebook object last stored (or read) on the server
  const inflight = useRef<Promise<void> | null>(null);
  const again = useRef(false);
  const timer = useRef<number | null>(null);

  const push = useCallback(async (): Promise<void> => {
    if (inflight.current) {
      again.current = true; // after the one in flight
      return inflight.current;
    }
    const nb = latest.current;
    if (nb === saved.current || current.current.kind === "conflict") return;
    const run = (async () => {
      setState({ kind: "saving" });
      const exit = await save({
        path: { id: nb.id },
        payload: { document: toDocument(nb), baseRevision: revisions.get(nb.id) },
        reactivityKeys: NOTES,
      });
      if (Exit.isSuccess(exit)) {
        revisions.set(nb.id, exit.value.revision);
        saved.current = nb;
        setState({ kind: "saved", at: exit.value.savedAt });
        return;
      }
      const error = failure(exit.cause);
      if (error?._tag === "RevisionConflict") setState({ kind: "conflict", current: error.current ?? 0 });
      else if (error?._tag === "RequestError" || error?._tag === "ResponseError" || error === null) {
        setState({ kind: "offline" });
        schedule(RETRY);
      } else setState({ kind: "error", message: error.message ?? String(error._tag) });
    })();
    inflight.current = run;
    try {
      await run;
    } finally {
      inflight.current = null;
    }
    if (again.current) {
      again.current = false;
      await push();
    }
  }, [save, setState]); // eslint-disable-line react-hooks/exhaustive-deps

  const schedule = (delay = DELAY) => {
    if (timer.current !== null) return;
    timer.current = window.setTimeout(() => {
      timer.current = null;
      void push();
    }, delay);
  };

  // a change: send it soon. At the start, only a notebook the server has never seen is sent
  // (one it knows is sent on its first change — opening a page is not an edit)
  const first = useRef(true);
  useEffect(() => {
    if (first.current) {
      first.current = false;
      if (revisions.get(notebook.id) !== null) return;
    }
    schedule();
  }, [notebook]); // eslint-disable-line react-hooks/exhaustive-deps

  /** Wait until what is on screen is on the server (before switching notes). */
  const flush = async () => {
    if (timer.current !== null) {
      clearTimeout(timer.current);
      timer.current = null;
    }
    await push();
  };

  const open = async (id: string) => {
    await flush();
    const exit = await get({ path: { id } });
    if (Exit.isFailure(exit)) {
      const error = failure(exit.cause);
      setState(error?._tag === "NoteNotFound" ? { kind: "error", message: `Nie ma już notatki ${id}.` } : { kind: "offline" });
      return;
    }
    const nb = fromDocument(exit.value.document);
    revisions.set(id, exit.value.revision);
    saved.current = nb;
    setState({ kind: "saved", at: exit.value.savedAt });
    replace(nb);
  };

  const create = async () => {
    await flush();
    setState({ kind: "idle" });
    replace(blank());
  };

  const destroy = async (id: string) => {
    const exit = await remove({ path: { id }, reactivityKeys: NOTES });
    if (Exit.isFailure(exit) && failure(exit.cause)?._tag !== "NoteNotFound") {
      setState({ kind: "offline" });
      return false;
    }
    revisions.set(id, null);
    if (latest.current.id === id) {
      setState({ kind: "idle" });
      replace(blank());
    }
    return true;
  };

  /** Conflict: keep what is on screen (it becomes the newest revision)… */
  const keepMine = async () => {
    if (state.kind !== "conflict") return;
    revisions.set(latest.current.id, state.current || null);
    saved.current = null;
    setState({ kind: "idle" });
    await push();
  };
  /** …or take what the server has. */
  const takeTheirs = async () => {
    setState({ kind: "idle" });
    saved.current = latest.current; // nothing to send before reading
    await open(latest.current.id);
  };

  return { state, open, create, destroy, keepMine, takeTheirs, flush };
}
