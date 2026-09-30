/**
 * The notes API (@electro/notes-api) served in the page, over the vault in this browser: the
 * notebook's client calls it as it would the notes server — ``apiFetch`` is its fetch. No one needs
 * to sign in (the user is this browser's; ``me`` is who connected GitHub, if anyone did); nothing is
 * shared (sharing's endpoints find nothing), and there are no notes from before folders.
 */
import { HttpApiBuilder, HttpServer } from "@effect/platform";
import {
  Authentication,
  CurrentUser,
  FIRMWARE_MAX,
  FirmwareNotFound,
  FirmwareSize,
  type Folder,
  type ItemCard,
  type MoveIntoItself,
  type NotAFolder,
  type Note,
  NoteIdMismatch,
  NotesApi,
  NotFound,
  type RevisionConflict,
  type Saved,
  Unauthorized,
  User,
  type UserId,
} from "@electro/notes-api";
import LightningFS from "@isomorphic-git/lightning-fs";
import { Effect, Layer } from "effect";
import { configured, connection, disconnect } from "./auth";
import * as L from "./library";
import { type Fs, Repo } from "./repo";
import { newId, Vault } from "./vault";
import { FS_NAME } from "./wipe";

let current: Vault | null = null;

/** The vault in this browser (IndexedDB). */
export const vault = () => (current ??= new Vault(new Repo(new LightningFS(FS_NAME) as unknown as Fs)));

/** Another vault (the tests'). */
export const useVault = (v: Vault) => {
  current = v;
};

const LOCAL = new User({ id: "local" as UserId, name: "", email: null, avatarUrl: null });

/** A call to the vault: the contract's errors as they are, anything else a defect. */
const run = <A, E = never>(f: () => Promise<A>): Effect.Effect<A, E> =>
  Effect.tryPromise({ try: f, catch: (e) => e }).pipe(
    Effect.catchAll((e) => (e instanceof Error && "_tag" in e ? Effect.fail(e as E) : Effect.die(e))),
  );

const AuthenticationLive = Layer.succeed(
  Authentication,
  Authentication.of({
    session: () =>
      Effect.sync(() => {
        const c = connection();
        return c
          ? new User({ id: String(c.id) as UserId, name: c.name, email: c.email, avatarUrl: c.avatarUrl })
          : LOCAL;
      }),
  }),
);

const LibraryLive = HttpApiBuilder.group(NotesApi, "library", (handlers) =>
  handlers
    .handle("home", () => run(async () => L.home(await vault().read())))
    .handle("folder", ({ path }) => run<Folder, NotFound>(async () => L.folder(await vault().read(), path.id)))
    .handle("destinations", () => run(async () => L.destinations(await vault().read())))
    .handle("createFolder", ({ payload }) =>
      run<ItemCard, NotFound | NotAFolder>(() => vault().createFolder(newId(), payload.name, payload.parentId)),
    )
    .handle("note", ({ path }) => run<Note, NotFound>(() => vault().note(path.id)))
    .handle("save", ({ path, payload }) =>
      payload.document.id !== path.id
        ? Effect.fail(new NoteIdMismatch({ path: path.id, document: payload.document.id }))
        : run<Saved, NotFound | NotAFolder | RevisionConflict>(() =>
            vault().save(payload.document, payload.baseRevision, payload.parentId),
          ),
    )
    .handle("patch", ({ path, payload }) =>
      run<ItemCard, NotFound | NotAFolder | MoveIntoItself>(() => vault().patch(path.id, payload)),
    )
    .handle("remove", ({ path }) => run<void, NotFound>(() => vault().remove(path.id)))
    .handle("legacy", ({ path }) => Effect.fail(new NotFound({ id: path.ref }))),
);

const SharingLive = HttpApiBuilder.group(NotesApi, "sharing", (handlers) => {
  const none = ({ path }: { path: { id: string } | { token: string } }) =>
    Effect.fail(new NotFound({ id: "id" in path ? path.id : path.token }));
  return handlers
    .handle("get", none)
    .handle("add", none)
    .handle("setRole", none)
    .handle("unshare", none)
    .handle("leave", none)
    .handle("link", none)
    .handle("newLink", none)
    .handle("unlink", none)
    .handle("join", none);
});

const AuthLive = HttpApiBuilder.group(NotesApi, "auth", (handlers) =>
  handlers
    .handle("providers", () => Effect.succeed(configured() ? (["github"] as const) : []))
    .handle("me", () =>
      Effect.flatMap(CurrentUser, (user) => (user === LOCAL ? Effect.fail(new Unauthorized()) : Effect.succeed(user))),
    )
    .handle("logout", () => Effect.sync(disconnect))
    // (connecting is auth.ts': the browser goes to GitHub itself)
    .handle("login", () => Effect.die("not in the page"))
    .handle("callback", () => Effect.die("not in the page")),
);

const SystemLive = HttpApiBuilder.group(NotesApi, "system", (handlers) =>
  handlers.handle("health", () => Effect.succeed({ ok: true as const })),
);

const FirmwareLive = HttpApiBuilder.group(NotesApi, "firmware", (handlers) =>
  handlers.handle("upload", ({ payload }) => {
    const size = payload.length;
    if (size === 0 || size > FIRMWARE_MAX) return Effect.fail(new FirmwareSize({ size, max: FIRMWARE_MAX }));
    return run(async () => {
      const digest = new Uint8Array(await crypto.subtle.digest("SHA-256", payload as Uint8Array<ArrayBuffer>));
      const id = Array.from(digest, (b) => b.toString(16).padStart(2, "0")).join("");
      await vault().putFirmware(id, payload); // (kept once: the same file again is there already)
      return { id, size };
    });
  }),
);

const FirmwareFilesLive = HttpApiBuilder.group(NotesApi, "firmwareFiles", (handlers) =>
  handlers.handle("get", ({ path }) =>
    run<Uint8Array, FirmwareNotFound>(async () => {
      const bytes = /^[0-9a-f]{64}$/.test(path.id) ? await vault().firmware(path.id) : null;
      if (bytes === null) throw new FirmwareNotFound({ id: path.id });
      return bytes;
    }),
  ),
);

const ApiLive = HttpApiBuilder.api(NotesApi).pipe(
  Layer.provide([LibraryLive, SharingLive, AuthLive, SystemLive, FirmwareLive, FirmwareFilesLive]),
  Layer.provide(AuthenticationLive),
);

const { handler } = HttpApiBuilder.toWebHandler(Layer.mergeAll(ApiLive, HttpServer.layerContext));

/** fetch, for the notes API's addresses (/api/…): answered in the page. */
export const apiFetch: typeof fetch = (input, init) => handler(new Request(input, init));
