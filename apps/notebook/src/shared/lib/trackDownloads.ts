/// <reference lib="webworker" />
// In a worker: every file it fetches, counted as it arrives and told to the page (the downloads'
// indicator, features/downloads) — Pyodide's own fetches too, so this wraps fetch itself.

/** What a worker tells the page about one file: which group it is in (what it is for), how far. */
export interface Progress {
  key: string; // its address
  group: string; // "python", "compiler", "uno", "pico"
  name: string; // its file's name
  loaded: number; // bytes so far
  total: number; // bytes it said it has (0: it did not say; compressed, it may say fewer than come)
  done: boolean;
  error?: string;
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
    let loaded = 0;
    let told = 0;
    tell({ loaded, total, done: false });
    const counter = new TransformStream<Uint8Array, Uint8Array>({
      transform(chunk, out) {
        loaded += chunk.byteLength;
        if (performance.now() - told > 100) {
          told = performance.now();
          tell({ loaded, total, done: false });
        }
        out.enqueue(chunk);
      },
      flush() {
        tell({ loaded, total, done: true });
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
