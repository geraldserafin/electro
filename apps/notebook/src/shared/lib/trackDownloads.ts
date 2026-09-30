/// <reference lib="webworker" />
// In a worker: every file it fetches, counted as it arrives and told to the page (the downloads'
// indicator, features/downloads) — Pyodide's own fetches too, so this wraps fetch itself. Only what
// comes over the network: a file the browser had (its cache: read in a moment, nothing transferred)
// is not told at all — else each visit would look like downloading it all again.
//
// The tools (Pyodide and its packages, the compiler, Typst's fonts) are also kept in the site's own
// storage (the Cache API): the browser's HTTP cache may be emptied any time (by its size, or on closing
// the browser), the site's storage is kept — for good once the site may store persistently.

/** What a worker tells the page about one file: which group it is in (what it is for), how far. */
export interface Progress {
  key: string; // its address
  group: string; // "python", "compiler", "uno", "pico"
  name: string; // its file's name
  loaded: number; // bytes so far
  total: number; // bytes it said it has (0: it did not say; compressed, it may say fewer than come)
  done: boolean;
  error?: string;
  cached?: boolean; // done, and it was in the browser's cache after all (read slowly): not a download
}

const QUIET = 300; // ms a file is not told for: by then one from the cache is mostly read

/** Whether a fetched file came from the browser's cache (nothing over the network); null: not known. */
function fromCache(url: string): boolean | null {
  const entry = performance.getEntriesByName(url).at(-1) as PerformanceResourceTiming | undefined;
  // (from the cache: nothing transferred, or only the headers of a 304 when it was asked whether it is
  // still the same; a cross-origin file without Timing-Allow-Origin says 0 for all)
  return entry && entry.encodedBodySize > 0 ? entry.transferSize < entry.encodedBodySize : null;
}

const KEPT = "electro-tools-v1";
const BASE = new URL(import.meta.env.BASE_URL, self.location.origin).href;

/** How a file is kept in the site's storage: "fixed" (its address names its version: kept as it is),
 *  "checked" (asked each time whether it is still the same — a 304, a few hundred bytes), null: not kept. */
function keeping(url: string, init?: RequestInit): "fixed" | "checked" | null {
  if ((init?.method ?? "GET") !== "GET" || init?.cache === "no-cache" || init?.cache === "no-store") return null;
  if (/\/pyodide\/v[\d.]+\//.test(url) || url.startsWith(`${BASE}assets/`)) return "fixed"; // (Vite's: hashed)
  if (url.startsWith(`${BASE}arduino/`) || url.startsWith(`${BASE}typst/`)) return "checked";
  return null;
}

let store: Promise<Cache | null> | null = null;
/** The site's storage for the tools (null: there is none, as in some private windows); older ones gone. */
function openStore(): Promise<Cache | null> {
  store ??= (async () => {
    try {
      for (const name of await caches.keys())
        if (name.startsWith("electro-tools-") && name !== KEPT) await caches.delete(name);
      return await caches.open(KEPT);
    } catch {
      return null;
    }
  })();
  return store;
}

/** A tool's file: from the site's storage when it has it (and it is still the same), else fetched and kept. */
async function keptFetch(
  fetch: typeof self.fetch,
  url: string,
  how: "fixed" | "checked",
  init?: RequestInit,
): Promise<{ response: Response; kept: boolean }> {
  const cache = await openStore();
  const stored = await cache?.match(url).catch(() => undefined);
  if (stored && how === "fixed") return { response: stored, kept: true };
  const etag = stored?.headers.get("etag");
  let response: Response;
  try {
    // (a conditional request goes past the HTTP cache: the server says whether it is the same)
    response = await fetch(url, etag ? { ...init, headers: { "If-None-Match": etag } } : init);
  } catch (e) {
    if (stored) return { response: stored, kept: true }; // offline: the one kept
    throw e;
  }
  if (response.status === 304 && stored) return { response: stored, kept: true };
  if (response.ok && cache) cache.put(url, response.clone()).catch(() => {});
  return { response, kept: false };
}

/** From now on, this worker's fetches (of files ``group`` names a group for) are counted. */
export function trackDownloads(group: (url: string) => string | null) {
  const original = self.fetch.bind(self);
  self.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(
      typeof input === "string" ? input : input instanceof URL ? input.href : input.url,
      self.location.href,
    ).href;
    const g = group(url);
    const name = decodeURIComponent(url.split("?")[0].split("/").pop() || url);
    const tell = (p: Omit<Progress, "key" | "group" | "name">) =>
      self.postMessage({ progress: { key: url, group: g ?? "", name, ...p } satisfies Progress });
    const how = keeping(url, init);
    let response: Response;
    try {
      if (how) {
        const got = await keptFetch(original, url, how, init);
        if (got.kept) return got.response; // (not a download)
        response = got.response;
      } else response = await original(input, init);
    } catch (e) {
      if (g) tell({ loaded: 0, total: 0, done: true, error: String(e) });
      throw e;
    }
    if (!g || !response.ok || !response.body) return response;
    const total = Number(response.headers.get("content-length")) || 0;
    const started = performance.now();
    let loaded = 0;
    let told = 0; // when last told (0: not yet)
    const counter = new TransformStream<Uint8Array, Uint8Array>({
      transform(chunk, out) {
        loaded += chunk.byteLength;
        const now = performance.now();
        if (now - started > QUIET && now - told > 100) {
          told = now;
          tell({ loaded, total, done: false });
        }
        out.enqueue(chunk);
      },
      flush() {
        // (its timing entry comes once the body is read: a moment later)
        setTimeout(() => {
          const cached = fromCache(url);
          if (told || cached === false || (cached === null && performance.now() - started > QUIET))
            tell({ loaded, total, done: true, cached: cached === true });
        });
      },
    });
    // the same response, its body counted (its headers kept: WebAssembly.compileStreaming wants its type)
    return new Response(response.body.pipeThrough(counter), {
      status: response.status,
      statusText: response.statusText,
      headers: response.headers,
    });
  };
}
