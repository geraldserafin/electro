/// <reference lib="webworker" />
// In a worker: every file it fetches, counted as it arrives and told to the page (the downloads'
// indicator, features/downloads) — Pyodide's own fetches too, so this wraps fetch itself. Only what
// comes over the network: a file the browser had (its cache: read in a moment, nothing transferred)
// is not told at all — else each visit would look like downloading it all again.

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

/** From now on, this worker's fetches (of files ``group`` names a group for) are counted. */
export function trackDownloads(group: (url: string) => string | null) {
  const original = self.fetch.bind(self);
  self.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    const g = group(url);
    const name = decodeURIComponent(url.split("?")[0].split("/").pop() || url);
    const tell = (p: Omit<Progress, "key" | "group" | "name">) =>
      self.postMessage({ progress: { key: url, group: g ?? "", name, ...p } satisfies Progress });
    let response: Response;
    try {
      response = await original(input, init);
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
