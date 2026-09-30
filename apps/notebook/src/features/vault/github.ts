/**
 * What the vault asks GitHub's REST API (the git side is repo.ts'): who the token is, and their
 * private repository electro-notes — made the first time they connect.
 */
const API = "https://api.github.com";
export const VAULT = "electro-notes";

export class GitHubError extends Error {
  constructor(
    readonly status: number,
    body: string,
  ) {
    super(`GitHub: HTTP ${status}: ${body.slice(0, 300)}`);
  }
}

async function call<A>(token: string, method: string, path: string, body?: unknown): Promise<A> {
  const response = await fetch(API + path, {
    method,
    cache: "no-store",
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/vnd.github+json",
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
    },
    body: body === undefined ? null : JSON.stringify(body),
  });
  if (!response.ok) throw new GitHubError(response.status, await response.text());
  return response.json() as Promise<A>;
}

export interface Profile {
  id: number;
  login: string;
  name: string;
  email: string | null;
  avatarUrl: string | null;
}

export async function profile(token: string): Promise<Profile> {
  const me = await call<{ id: number; login: string; name: string | null; email: string | null; avatar_url: string }>(
    token,
    "GET",
    "/user",
  );
  return { id: me.id, login: me.login, name: me.name || me.login, email: me.email, avatarUrl: me.avatar_url ?? null };
}

/** The user's vault on GitHub (made, private and empty, if they have none): its git address, whether
 *  its main is there yet (``empty``: not — whatever other branches, an autosave's say, there are). */
export async function vaultRepo(token: string, login: string): Promise<{ url: string; empty: boolean }> {
  const repo = `${login}/${VAULT}`;
  let info: { default_branch: string };
  try {
    info = await call(token, "GET", `/repos/${repo}`);
  } catch (e) {
    if (!(e instanceof GitHubError && e.status === 404)) throw e;
    info = await call(token, "POST", "/user/repos", { name: VAULT, private: true, description: "Notes from Electro" });
  }
  const branches = await call<{ name: string }[]>(token, "GET", `/repos/${repo}/branches`);
  const main = branches.some((b) => b.name === MAIN);
  // (the first branch pushed to an empty repository becomes its default: main, not an autosave's)
  if (main && info.default_branch !== MAIN) await call(token, "PATCH", `/repos/${repo}`, { default_branch: MAIN });
  return { url: `https://github.com/${repo}.git`, empty: !main };
}

const MAIN = "main";
