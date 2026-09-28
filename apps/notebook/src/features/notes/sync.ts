// Saving the note on /notes/:id to the notes server as it is edited.
//
// Every change is sent at most a second after it happens, with the revision the note was read
// at; one save is in flight at a time (a second one waits), so revisions never cross. A conflict
// — the note changed elsewhere — stops saving until the user picks a version. When the server
// cannot be reached, saving is retried; what is pending is sent when the page is left.
import { useAtomSet } from "@effect-atom/atom-react";
import { Cause, Exit, Option } from "effect";
import { useCallback, useEffect, useRef, useState } from "react";
import type { Notebook } from "@/shared/model/types";
import { LIBRARY, saveNote, toDocument } from "./atoms";

export type SyncState =
  | { kind: "idle" } // nothing to send
  | { kind: "saving" }
  | { kind: "saved"; at: string }
  | { kind: "offline" } // the server is unreachable: retried
  | { kind: "conflict"; current: number } // changed elsewhere since it was read
  | { kind: "error"; tag: string }; // the server's error (its _tag), said by SyncNotice

const DELAY = 1000;
const RETRY = 10_000;

/** The error a failed call ended with, if it is one of ours (tagged); null for transport and defects. */
export function failure(cause: Cause.Cause<unknown>): { _tag?: string; current?: number; message?: string } | null {
  return (Option.getOrNull(Cause.failureOption(cause)) as { _tag?: string } | null) ?? null;
}

const unreachable = (error: { _tag?: string } | null) =>
  error === null || error._tag === "RequestError" || error._tag === "ResponseError";

/**
 * ``revision``: what the note was read at (null: not on the server yet); ``reload``: read the
 * note again (to take the server's version after a conflict); ``readOnly``: shared with the user
 * to read — changes stay on the page.
 */
export function useNoteSync(notebook: Notebook, revision: number | null, reload: () => void, readOnly = false) {
  const [state, setState] = useState<SyncState>({ kind: "idle" });
  const save = useAtomSet(saveNote, { mode: "promiseExit" });

  const latest = useRef(notebook);
  latest.current = notebook;
  const base = useRef(revision);
  const conflict = useRef(false);
  const sent = useRef<Notebook>(notebook); // the version the server has (as loaded, at first)
  const inflight = useRef<Promise<void> | null>(null);
  const again = useRef(false);
  const timer = useRef<number | null>(null);

  const push = useCallback(async (): Promise<void> => {
    if (inflight.current) {
      again.current = true; // after the one in flight
      return inflight.current;
    }
    const nb = latest.current;
    if ((nb === sent.current && base.current !== null) || conflict.current) return;
    const run = (async () => {
      setState({ kind: "saving" });
      const exit = await save({
        path: { id: nb.id },
        payload: { document: toDocument(nb), baseRevision: base.current },
        reactivityKeys: LIBRARY,
      });
      if (Exit.isSuccess(exit)) {
        base.current = exit.value.revision;
        sent.current = nb;
        setState({ kind: "saved", at: exit.value.savedAt });
        return;
      }
      const error = failure(exit.cause);
      if (error?._tag === "RevisionConflict") {
        conflict.current = true;
        setState({ kind: "conflict", current: error.current ?? 0 });
      } else if (unreachable(error)) {
        setState({ kind: "offline" });
        schedule(RETRY);
      } else setState({ kind: "error", tag: String(error?._tag) });
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
  }, [save]); // eslint-disable-line react-hooks/exhaustive-deps

  const schedule = (delay = DELAY) => {
    if (timer.current !== null || readOnly) return; // a viewer's changes stay on the page
    timer.current = window.setTimeout(() => {
      timer.current = null;
      void push();
    }, delay);
  };

  // a change: sent a moment later (opening a note is not a change)
  const first = useRef(true);
  useEffect(() => {
    if (first.current) {
      first.current = false;
      if (base.current !== null) return;
    }
    schedule();
  }, [notebook]); // eslint-disable-line react-hooks/exhaustive-deps

  // leaving the page (another note, the list): send what is pending
  useEffect(() => () => {
    if (timer.current !== null) {
      clearTimeout(timer.current);
      timer.current = null;
      void push();
    }
  }, [push]);

  // closing the tab with changes not on the server yet: the browser asks first
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => {
      if (timer.current !== null || inflight.current || state.kind === "offline" || state.kind === "conflict")
        event.preventDefault();
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [state]);

  /** Conflict: keep what is on screen (it becomes the newest revision)… */
  const keepMine = async () => {
    if (state.kind !== "conflict") return;
    base.current = state.current || null;
    conflict.current = false;
    sent.current = null as unknown as Notebook; // whatever is on screen is new to the server
    setState({ kind: "idle" });
    await push();
  };
  /** …or take what the server has. */
  const takeTheirs = reload;

  return { state, keepMine, takeTheirs };
}
