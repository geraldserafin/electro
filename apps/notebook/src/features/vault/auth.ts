/**
 * Connecting GitHub (an OAuth app with the `repo` scope: the vault goes to a private repository).
 * The browser goes to GitHub's consent screen and comes back to /auth/callback with a code; the auth
 * worker (apps/auth-worker, which holds the app's secret) trades it for a token. The token and who it
 * is are kept in this browser until the user disconnects — the notebook needs no GitHub to work.
 *
 *   VITE_GITHUB_CLIENT_ID  the OAuth app's client id (none: connecting is off)
 *   VITE_AUTH_URL          the auth worker (by default `wrangler dev`'s address)
 */
import i18next from "i18next";
import { type Profile, profile } from "./github";
import { wipe } from "./wipe";

const CLIENT_ID = import.meta.env.VITE_GITHUB_CLIENT_ID as string | undefined;
export const AUTH_URL = (import.meta.env.VITE_AUTH_URL as string | undefined) ?? "http://localhost:8787";

const KEY = "electro.github";
/** Whose vault on GitHub the notes here were last saved to. */
export const OWNER = "electro.vault-owner";
const FLOW = "electro.github-connect"; // the connecting under way: its state, where to come back to

export const CALLBACK = `${import.meta.env.BASE_URL}auth/callback`;

export const configured = () => Boolean(CLIENT_ID);

export interface Connection extends Profile {
  token: string;
}

export function connection(): Connection | null {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? "null") as Connection | null;
  } catch {
    return null;
  }
}

export function disconnect() {
  localStorage.removeItem(KEY);
}

/** Off to GitHub; back at ``returnTo`` (a path here), connected. */
export function connect(returnTo: string) {
  const state = crypto.randomUUID();
  sessionStorage.setItem(FLOW, JSON.stringify({ state, returnTo }));
  const url = new URL("https://github.com/login/oauth/authorize");
  url.search = new URLSearchParams({
    client_id: CLIENT_ID ?? "",
    scope: "repo",
    state,
    redirect_uri: new URL(CALLBACK, location.origin).href,
  }).toString();
  location.assign(url);
}

/** On /auth/callback: the token for the code GitHub sent, then the address the connecting started
 *  at (?github=failed when it did not work); true when it connected. Elsewhere: nothing. */
export async function finishConnecting(): Promise<boolean> {
  if (location.pathname !== CALLBACK) return false;
  const params = new URLSearchParams(location.search);
  const flow = JSON.parse(sessionStorage.getItem(FLOW) ?? "null") as { state: string; returnTo: string } | null;
  sessionStorage.removeItem(FLOW);
  const back = (path: string) => history.replaceState(null, "", path);
  const returnTo =
    flow?.returnTo.startsWith("/") && !flow.returnTo.startsWith("//") ? flow.returnTo : import.meta.env.BASE_URL;
  const code = params.get("code");
  if (params.get("error")) {
    back(returnTo); // they said no
    return false;
  }
  if (!code || !flow || params.get("state") !== flow.state) {
    back(`${returnTo}?github=failed`);
    return false;
  }
  try {
    const response = await fetch(`${AUTH_URL}/token`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code }),
    });
    const { access_token } = (await response.json()) as { access_token?: string };
    if (!access_token) throw new Error(`auth worker: HTTP ${response.status}`);
    const connected: Connection = { ...(await profile(access_token)), token: access_token };
    // the notes here came from another account's vault: joined with this one's only if the user says so
    const owner = localStorage.getItem(OWNER);
    if (owner && owner !== connected.login) {
      if (!confirm(i18next.t("auth:otherAccount", { from: owner, to: connected.login }))) await wipe();
      localStorage.removeItem(OWNER);
    }
    localStorage.setItem(KEY, JSON.stringify(connected));
    back(returnTo);
    return true;
  } catch (e) {
    console.warn("Connecting GitHub did not work", e);
    back(`${returnTo}?github=failed`);
    return false;
  }
}
