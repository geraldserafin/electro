/**
 * Saving the vault. What the notebook changes is in the vault's files at once; from there:
 *
 *   autosave   a moment after the changes stop (and at most every few minutes while they go on, and
 *              when the page goes to the background): the session's one commit, amended, and with
 *              GitHub connected pushed to this browser's own branch (autosave/<device>) — safe on
 *              GitHub, but not in the vault's history yet
 *   save       the button, ⌘S, a long pause, the next time the app opens: the session over — its
 *              commit joined with GitHub's main and pushed there. One commit a session, then.
 *
 * Editors give a flush (``onSave``): what they have not written yet, written first. The other tabs
 * of the vault hear of every change (and read it afresh). The state, for the save button: changes
 * not autosaved yet, a session not saved yet, saving, what went wrong.
 */
import i18next from "i18next";
import { useSyncExternalStore } from "react";
import { vault } from "./api";
import { AUTH_URL, connection, OWNER } from "./auth";
import { GitHubError, VAULT, vaultRepo } from "./github";

export interface SaveState {
  readonly pending: boolean; // changes not autosaved yet
  readonly open: boolean; // a session not saved yet (autosaved: safe, but not in the history)
  readonly saving: boolean;
  readonly error: "auth" | "failed" | null; // "auth": GitHub does not take the token any more
  readonly detail: string | null; // what went wrong, as the error said it (for the notice)
}

const AUTOSAVE = 10_000; // after the last change
const AUTOSAVE_AT_MOST = 120_000; // after the first one, however many follow
const SESSION = 30 * 60_000; // no change for this long: the session is saved

let state: SaveState = { pending: false, open: false, saving: false, error: null, detail: null };
const listeners = new Set<() => void>();
const set = (next: Partial<SaveState>) => {
  state = { ...state, ...next };
  for (const l of listeners) l();
};
const subscribe = (l: () => void) => {
  listeners.add(l);
  return () => listeners.delete(l);
};
export const useSaveState = () => useSyncExternalStore(subscribe, () => state);

const flushers = new Set<() => Promise<void>>();
/** What an editor has not written yet, written before saving; off again with the function returned. */
export function onSave(flush: () => Promise<void>) {
  flushers.add(flush);
  return () => {
    flushers.delete(flush);
  };
}

/** This browser's name for its autosave branch. */
function device(): string {
  let id = localStorage.getItem("electro.device");
  if (!id) localStorage.setItem("electro.device", (id = crypto.randomUUID().slice(0, 8)));
  return id;
}

async function github() {
  const c = connection();
  if (!c) return { author: { name: "Electro", email: "electro@localhost" }, remote: null, login: null };
  return {
    author: { name: c.name, email: `${c.id}+${c.login}@users.noreply.github.com` },
    remote: { ...(await vaultRepo(c.token, c.login)), token: c.token, corsProxy: `${AUTH_URL}/git` },
    login: c.login,
  };
}

const failed = (e: unknown) => {
  console.warn("Saving did not work", e);
  const status = e instanceof GitHubError ? e.status : (e as { data?: { statusCode?: number } }).data?.statusCode;
  const detail = e instanceof Error ? e.message.slice(0, 200) : String(e);
  return { saving: false, error: status === 401 ? ("auth" as const) : ("failed" as const), detail };
};

/** Tells this page (the lists, a note open here) and the other tabs that notes changed. */
const channel = typeof BroadcastChannel === "undefined" ? null : new BroadcastChannel("electro-vault");
function changed(notes: string[], others: boolean) {
  window.dispatchEvent(new CustomEvent("electro:pulled", { detail: notes }));
  if (others) channel?.postMessage(notes);
}

// ------------------------------------------------------------------ the two kinds of saving

let busy: Promise<unknown> = Promise.resolve();
const oneAtATime = <A>(f: () => Promise<A>) => {
  const next = busy.then(f, f);
  busy = next.catch(() => {});
  return next;
};

async function autosave() {
  clear();
  if (!state.pending) return;
  await oneAtATime(async () => {
    set({ saving: true });
    try {
      await Promise.all([...flushers].map((f) => f()));
      const { author, remote } = await github();
      await vault().autosave(author, remote, device());
      set({ saving: false, pending: false, open: true, error: null, detail: null });
    } catch (e) {
      set(failed(e));
    }
  });
}

/** The session saved and over; with GitHub, joined with its main (what came from there, shown). */
export function save(): Promise<boolean> {
  clear();
  return oneAtATime(async () => {
    set({ saving: true, error: null, detail: null });
    try {
      await Promise.all([...flushers].map((f) => f()));
      const { author, remote, login } = await github();
      const copy = (title: string) => i18next.t("notes:save.copyTitle", { title });
      const pulled = await vault().finish(author, remote, device(), copy);
      if (remote?.empty && login) {
        // main made just now: the default branch, and an autosave branch from before it gone
        await vaultRepo(remote.token, login);
        await vault().repo.dropSessionBranch(remote, device());
      }
      if (login) localStorage.setItem(OWNER, login);
      set({ saving: false, pending: false, open: false });
      changed(pulled, pulled.length > 0);
      return true;
    } catch (e) {
      set(failed(e));
      return false;
    }
  });
}

let autosaveTimer: number | undefined;
let firstChange: number | null = null;
let sessionTimer: number | undefined;
function clear() {
  clearTimeout(autosaveTimer);
  firstChange = null;
}

function schedule() {
  const now = Date.now();
  firstChange ??= now;
  clearTimeout(autosaveTimer);
  autosaveTimer = window.setTimeout(autosave, Math.min(AUTOSAVE, firstChange + AUTOSAVE_AT_MOST - now));
  clearTimeout(sessionTimer);
  sessionTimer = window.setTimeout(save, SESSION);
}

let started = false;
/** Saving from now on — and first, the session from before saved (with GitHub: what is new there brought in). */
export function startSaving() {
  if (started) return;
  started = true;
  navigator.storage?.persist?.().catch(() => {}); // (the browser keeps the vault even when short of space)
  vault().onChange = (notes) => {
    set({ pending: true });
    schedule();
    channel?.postMessage(notes);
  };
  if (channel)
    channel.onmessage = (e: MessageEvent<string[]>) => {
      vault().external(e.data);
      changed(e.data, false);
    };
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") void autosave();
  });
  void save();
}

/** For the save button's card: what a save would put in, the history, and where it goes. */
export async function saveDetails() {
  const details = await vault().details();
  const c = connection();
  return { ...details, github: c ? { login: c.login, url: `https://github.com/${c.login}/${VAULT}` } : null };
}
export type SaveDetails = Awaited<ReturnType<typeof saveDetails>>;
