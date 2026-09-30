/**
 * The vault's git repository in the browser (isomorphic-git, over a file system in IndexedDB): its
 * files are what the notebook reads and writes as it goes; saving commits them, and — with GitHub
 * connected — joins GitHub's commits (merge.ts) and pushes. GitHub lets no page talk git to it
 * directly (no CORS), so that goes through the auth worker (its /git/…).
 */
import "./buffer";
import git from "isomorphic-git";
import http from "isomorphic-git/http/web";
import { type Changes, merge, type Tree } from "./merge";

/** The file system isomorphic-git works on (LightningFS in the page, node's in the tests). */
export type Fs = Parameters<typeof git.init>[0]["fs"] & {
  promises: {
    readFile(path: string): Promise<Uint8Array | string>;
    writeFile(path: string, data: Uint8Array | string): Promise<void>;
    unlink(path: string): Promise<void>;
    readdir(path: string): Promise<string[]>;
    mkdir(path: string): Promise<void>;
    stat(path: string): Promise<unknown>;
  };
};

export interface Author {
  name: string;
  email: string;
}

export interface Remote {
  url: string; // https://github.com/<owner>/<repo>.git
  token: string;
  corsProxy: string;
  empty: boolean; // nothing on it yet: nothing to fetch
}

const BRANCH = "main";
const THEIRS = `refs/remotes/origin/${BRANCH}`;
const SESSION = "refs/electro/session"; // the session's commit (repo.ts: commitSession)
const backup = (device: string) => `refs/heads/autosave/${device}`;

export type Change = "add" | "edit" | "delete";

const missing = (e: unknown) =>
  (e as { code?: string })?.code === "ENOENT" || (e as { code?: string })?.code === "NotFoundError";

export class Repo {
  constructor(
    readonly fs: Fs,
    readonly dir = "/vault",
  ) {}

  private get opts() {
    return { fs: this.fs, dir: this.dir };
  }

  async init() {
    try {
      await this.fs.promises.stat(`${this.dir}/.git`);
    } catch {
      await this.mkdirs(this.dir);
      await git.init({ ...this.opts, defaultBranch: BRANCH });
    }
  }

  // ------------------------------------------------------------------ the files

  async read(path: string): Promise<Uint8Array | null> {
    try {
      const data = await this.fs.promises.readFile(`${this.dir}/${path}`);
      return typeof data === "string" ? new TextEncoder().encode(data) : new Uint8Array(data);
    } catch (e) {
      if (missing(e)) return null;
      throw e;
    }
  }

  async write(path: string, data: Uint8Array | string) {
    await this.mkdirs(`${this.dir}/${path}`.split("/").slice(0, -1).join("/"));
    await this.fs.promises.writeFile(`${this.dir}/${path}`, data);
  }

  async remove(path: string) {
    try {
      await this.fs.promises.unlink(`${this.dir}/${path}`);
    } catch (e) {
      if (!missing(e)) throw e;
    }
  }

  /** The names in a folder of the vault (none: it is not there). */
  async list(path: string): Promise<string[]> {
    try {
      return await this.fs.promises.readdir(`${this.dir}/${path}`);
    } catch (e) {
      if (missing(e)) return [];
      throw e;
    }
  }

  private async mkdirs(path: string) {
    let at = "";
    for (const part of path.split("/").filter(Boolean)) {
      at += `/${part}`;
      try {
        await this.fs.promises.mkdir(at);
      } catch (e) {
        if ((e as { code?: string }).code !== "EEXIST") throw e;
      }
    }
  }

  // ------------------------------------------------------------------ commits

  private async head(ref = "HEAD"): Promise<string | null> {
    try {
      return await git.resolveRef({ ...this.opts, ref });
    } catch (e) {
      if (missing(e)) return null;
      throw e;
    }
  }

  /** The files as they are now (not only staged) against a commit (null: none): for showing what a
   *  save would put in. (Stat-based: an edit of the same size in the same second may show late.) */
  async workingChangesSince(commit: string | null): Promise<Record<string, Change>> {
    const out: Record<string, Change> = {};
    if (commit === null) {
      for (const path of await this.files()) out[path] = "add";
      return out;
    }
    // (h: in the commit; w: in the working directory — 0 gone, 1 as in the commit, 2 changed)
    for (const [path, h, w] of await git.statusMatrix({ ...this.opts, ref: commit })) {
      if (h === 0 && w !== 0) out[path] = "add";
      else if (h === 1 && w === 0) out[path] = "delete";
      else if (h === 1 && w === 2) out[path] = "edit";
    }
    return out;
  }

  /** The last commits of the history up to ``commit`` (newest first), and which of them are on
   *  GitHub's main already (as last fetched). */
  async history(
    commit: string | null,
    depth = 8,
  ): Promise<{ oid: string; message: string; time: number; onGitHub: boolean }[]> {
    if (!commit) return [];
    const [log, theirs] = await Promise.all([
      git.log({ ...this.opts, ref: commit, depth }),
      this.head(THEIRS).then((t) => (t ? git.log({ ...this.opts, ref: t, depth: 200 }) : [])),
    ]);
    const remote = new Set(theirs.map((c) => c.oid));
    return log.map((c) => ({
      oid: c.oid,
      message: c.commit.message.trim(),
      time: c.commit.author.timestamp * 1000,
      onGitHub: remote.has(c.oid),
    }));
  }

  /** When the session's commit was last amended (an autosave), if a session is open. */
  async autosavedAt(): Promise<number | null> {
    const session = await this.session();
    if (!session) return null;
    const { commit } = await git.readCommit({ ...this.opts, oid: session });
    return commit.author.timestamp * 1000;
  }

  /** The staged files against a commit (null: none): what was added, edited, deleted. */
  async changesSince(commit: string | null): Promise<Record<string, Change>> {
    const out: Record<string, Change> = {};
    if (commit === null) {
      for (const path of await git.listFiles(this.opts)) out[path] = "add";
      return out;
    }
    // (h: in the commit; s: staged — 1 as in the commit, 0 not there, else changed)
    for (const [path, h, , s] of await git.statusMatrix({ ...this.opts, ref: commit })) {
      if (h === 0 && s !== 0) out[path] = "add";
      else if (h === 1 && s === 0) out[path] = "delete";
      else if (h === 1 && s !== 1) out[path] = "edit";
    }
    return out;
  }

  /** Every file of the vault (not git's own). */
  private async files(prefix = ""): Promise<string[]> {
    const out: string[] = [];
    for (const name of await this.list(prefix)) {
      if (!prefix && name === ".git") continue;
      const path = prefix ? `${prefix}/${name}` : name;
      let folder = true;
      try {
        await this.fs.promises.readdir(`${this.dir}/${path}`);
      } catch {
        folder = false;
      }
      if (folder) out.push(...(await this.files(path)));
      else out.push(path);
    }
    return out;
  }

  /** A file as a commit has it (null: not there). */
  async readAt(commit: string, path: string): Promise<Uint8Array | null> {
    try {
      return (await git.readBlob({ ...this.opts, oid: commit, filepath: path })).blob;
    } catch (e) {
      if (missing(e)) return null;
      throw e;
    }
  }

  /** Every change in the files, committed (none: nothing happens); the commit's id. */
  async commit(message: string, author: Author, parent?: string[]): Promise<string | null> {
    if (!(await this.stage()) && !parent) return null;
    return git.commit({ ...this.opts, message, author, ...(parent ? { parent } : {}) });
  }

  /**
   * The files' changes staged; whether the staged files differ from the head's. Every file is hashed
   * afresh: git's own way of telling a changed file — its size and time to the second — misses an
   * edit of the same size in the same second (only firmware files, named by what is in them, are
   * taken as they were once staged).
   */
  private async stage(): Promise<boolean> {
    const [files, staged] = await Promise.all([this.files(), git.listFiles(this.opts)]);
    const known = new Set(staged);
    const hash = files.filter((f) => !(f.startsWith("firmware/") && known.has(f)));
    if (hash.length) await git.add({ ...this.opts, filepath: hash });
    const present = new Set(files);
    for (const filepath of staged) if (!present.has(filepath)) await git.remove({ ...this.opts, filepath });
    const head = await this.head();
    if (head === null) return files.length > 0;
    return Object.keys(await this.changesSince(head)).length > 0;
  }

  // ------------------------------------------------------------------ the session's commit

  /** The commit of the session under way (every autosave amends it; it ends on saving), if the head is one. */
  async session(): Promise<string | null> {
    const [session, head] = await Promise.all([this.head(SESSION), this.head()]);
    return session !== null && session === head ? session : null;
  }

  /** Where the session began: the commit before its own (null: the vault's first). */
  async sessionBase(): Promise<string | null> {
    const session = await this.session();
    if (!session) return this.head();
    const { commit } = await git.readCommit({ ...this.opts, oid: session });
    return commit.parent[0] ?? null;
  }

  /**
   * The changes into the session's commit: amended if one is under way, else a new one (with
   * the message ``describe`` gives the whole session's changes). Nothing changed: nothing happens — and
   * a session whose changes all went back (its files as they were before it) has no commit at all.
   */
  async commitSession(
    describe: (changes: Record<string, Change>, base: string | null) => Promise<string>,
    author: Author,
  ): Promise<void> {
    if (!(await this.stage())) return; // nothing new
    const session = await this.session();
    const base = await this.sessionBase();
    const changes = await this.changesSince(base);
    const message = await describe(changes, base);
    if (session && base && !Object.keys(changes).length) {
      // (everything undone: the session's commit goes)
      await git.writeRef({ ...this.opts, ref: `refs/heads/${BRANCH}`, value: base, force: true });
      await this.endSession();
      await git.checkout({ ...this.opts, ref: BRANCH, force: true });
      return;
    }
    const oid = await git.commit({ ...this.opts, message, author, amend: session !== null });
    await git.writeRef({ ...this.opts, ref: SESSION, value: oid, force: true });
  }

  /** The session over: the next change starts a new commit. */
  async endSession() {
    await git.deleteRef({ ...this.opts, ref: SESSION }).catch(() => {});
  }

  // ------------------------------------------------------------------ GitHub

  private net(remote: Remote) {
    return {
      fs: this.fs,
      http,
      dir: this.dir,
      corsProxy: remote.corsProxy,
      onAuth: () => ({ username: remote.token, password: "x-oauth-basic" }),
    };
  }

  /** The session's commit on GitHub, on this browser's own branch (autosave/<device>): replaced each
   *  time (no one builds on it), gone when the session ends. */
  async pushSession(remote: Remote, device: string) {
    // (no main on GitHub yet: the session waits for it — the first save makes it, and it is the default)
    if (remote.empty || !(await this.session())) return;
    await git.addRemote({ ...this.opts, remote: "origin", url: remote.url, force: true });
    await git.push({ ...this.net(remote), remote: "origin", ref: BRANCH, remoteRef: backup(device), force: true });
  }

  async dropSessionBranch(remote: Remote, device: string) {
    await git.push({ ...this.net(remote), remote: "origin", remoteRef: backup(device), delete: true }).catch(() => {}); // (there was none)
  }

  /** Changes not committed yet, a session under way, or commits GitHub has not got (with ``remote``). */
  async unsaved(remote: boolean): Promise<boolean> {
    const matrix = await git.statusMatrix(this.opts);
    if (matrix.some(([, h, w, s]) => !(h === 1 && w === 1 && s === 1))) return true;
    if (await this.session()) return true;
    if (!remote) return false;
    const [ours, theirs] = await Promise.all([this.head(), this.head(THEIRS)]);
    return ours !== null && ours !== theirs;
  }

  /** A commit's files: path → blob id. */
  async tree(commit: string | null): Promise<Tree> {
    const files: Record<string, string> = {};
    if (commit === null) return files;
    const walk = async (oid: string, prefix: string) => {
      const { tree } = await git.readTree({ ...this.opts, oid });
      for (const entry of tree) {
        if (entry.type === "tree") await walk(entry.oid, `${prefix}${entry.path}/`);
        else if (entry.type === "blob") files[`${prefix}${entry.path}`] = entry.oid;
      }
    };
    await walk(commit, "");
    return files;
  }

  private blob = async (oid: string) => (await git.readBlob({ ...this.opts, oid })).blob;

  /**
   * GitHub's line (``theirs``) joined into ours: taken as it is when ours has nothing it lacks,
   * else merged (merge.ts) in a commit of both. The paths that changed here.
   */
  async integrate(
    theirs: string,
    author: Author,
    newId: () => string,
    copyTitle: (title: string) => string,
  ): Promise<string[]> {
    const ours = await this.head();
    if (ours === theirs) return [];
    const [base] = ours ? await git.findMergeBase({ ...this.opts, oids: [ours, theirs] }) : [];
    if (base === theirs) return []; // GitHub has nothing we lack
    const before = await this.tree(ours);
    if (!ours || base === ours) {
      // nothing here GitHub lacks: its line, as it is
      await git.writeRef({ ...this.opts, ref: `refs/heads/${BRANCH}`, value: theirs, force: true });
      await git.checkout({ ...this.opts, ref: BRANCH, force: true });
      return diff(before, await this.tree(theirs));
    }
    const [baseTree, theirTree] = await Promise.all([this.tree(base ?? null), this.tree(theirs)]);
    const changes: Changes = await merge(
      { base: baseTree, ours: before, theirs: theirTree },
      this.blob,
      newId,
      copyTitle,
    );
    for (const [path, data] of Object.entries(changes)) {
      if (data === null) await this.remove(path);
      else await this.write(path, data);
    }
    await this.commit("Merge the vault on GitHub", author, [ours, theirs]);
    return Object.keys(changes);
  }

  /** Our commits and GitHub's, joined, and pushed there; the paths that changed here. */
  async sync(remote: Remote, author: Author, newId: () => string, copyTitle: (title: string) => string) {
    const net = this.net(remote);
    await git.addRemote({ ...this.opts, remote: "origin", url: remote.url, force: true });
    const changed = new Set<string>();
    for (let attempt = 0; ; attempt++) {
      if (!remote.empty || attempt > 0) {
        await git.fetch({ ...net, remote: "origin", ref: BRANCH, singleBranch: true });
        const theirs = await this.head(THEIRS);
        if (theirs) for (const path of await this.integrate(theirs, author, newId, copyTitle)) changed.add(path);
      }
      const ours = await this.head();
      // nothing anywhere yet, or nothing GitHub lacks: no push
      if (ours === null || ours === (await this.head(THEIRS))) return [...changed];
      try {
        await git.push({ ...net, remote: "origin", ref: BRANCH });
        return [...changed];
      } catch (e) {
        // someone pushed in between: theirs again, then ours
        if ((e as { code?: string }).code !== "PushRejectedError" || attempt >= 2) throw e;
      }
    }
  }
}

function diff(a: Tree, b: Tree): string[] {
  return [...new Set([...Object.keys(a), ...Object.keys(b)])].filter((p) => a[p] !== b[p]);
}
