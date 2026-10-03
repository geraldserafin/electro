// Asking the model: from this page straight to OpenRouter, with the user's own key and model (kept in
// this browser only — sent nowhere but to OpenRouter). The model only asks for the page's tools; the
// page runs them.

/** A tool the model asks for (the page runs it): which, with what (JSON). */
export type AiToolCall = { id: string; type: "function"; function: { name: string; arguments: string } };

type Part = { type: "text"; text: string } | { type: "image_url"; image_url: { url: string } };
type Content = string | Part[];

export type AiMessage =
  | { role: "system" | "user"; content: Content }
  | { role: "assistant"; content: string | null; tool_calls?: AiToolCall[] }
  | { role: "tool"; tool_call_id: string; content: Content }; // what a tool gave back

/** A tool the page offers the model: its name, what it does, its arguments (a JSON Schema). */
export type AiTool = {
  type: "function";
  function: { name: string; description: string; parameters: unknown };
};

export interface AiSettings {
  key: string; // "": none yet (asked for in the chat)
  model: string;
}

const STORE = "electro.ai";
// measured 2026-10 on a 7-page worksheet: Gemini 3.8 Flash drew 8 of 10 circuits right in 17 s for $0.03;
// Claude Sonnet 5.5 all 10, in 107 s for $0.21
export const DEFAULT_MODEL = "google/gemini-3.8-flash";

export function aiSettings(): AiSettings {
  try {
    const saved = JSON.parse(localStorage.getItem(STORE) ?? "{}") as Partial<AiSettings>;
    return { key: saved.key ?? "", model: saved.model?.trim() || DEFAULT_MODEL };
  } catch {
    return { key: "", model: DEFAULT_MODEL };
  }
}

export function saveAiSettings(settings: AiSettings) {
  try {
    localStorage.setItem(STORE, JSON.stringify({ key: settings.key.trim(), model: settings.model.trim() }));
  } catch {
    /* a private window: for this page only */
  }
}

/** Why there is no answer: no key, a key OpenRouter refuses, no credit left on it, or the model failed. */
export class AiError extends Error {
  constructor(readonly reason: "NoKey" | "BadKey" | "NoCredit" | "failed") {
    super(reason);
  }
}

/** What the model writes, as it comes: its thinking, and its answer so far. */
export type Progress = { thinking: string; content: string };

/** The model asked (its ``tools`` offered), its answer streamed (``onProgress`` with each piece): what it
 *  wrote, the tools it calls, and what it cost (dollars, as OpenRouter says; 0 when it does not). */
export async function complete(
  messages: AiMessage[],
  tools: AiTool[] = [],
  onProgress: (now: Progress) => void = () => {},
): Promise<{ content: string; calls: AiToolCall[]; cost: number }> {
  const { key, model } = aiSettings();
  if (!key) throw new AiError("NoKey");
  const response = await fetch("https://openrouter.ai/api/v1/chat/completions", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${key}`,
      "Content-Type": "application/json",
      "HTTP-Referer": location.origin,
      "X-Title": "electro",
    },
    // reasoning kept short: a model thinking without end left no room to answer (a worksheet's photo:
    // 8 000 tokens of thought, nothing said)
    body: JSON.stringify({
      model,
      messages,
      ...(tools.length ? { tools } : {}),
      stream: true,
      max_tokens: 16_000,
      reasoning: { effort: "minimal" },
      provider: { sort: "throughput" },
      usage: { include: true },
    }),
    signal: AbortSignal.timeout(180_000),
  }).catch(() => null);
  if (!response) throw new AiError("failed");
  if (response.status === 401) throw new AiError("BadKey");
  if (response.status === 402) throw new AiError("NoCredit");
  if (!response.ok || !response.body) throw new AiError("failed");

  const now: Progress = { thinking: "", content: "" };
  // the tools' calls, by their index, as they come in pieces (its id and name first, its arguments after)
  const calls: AiToolCall[] = [];
  let cost = 0;
  let failed = false;
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read().catch(() => ({ value: undefined, done: true }));
    if (done) break;
    buffer += value;
    const lines = buffer.split("\n");
    buffer = lines.pop()!;
    for (const line of lines) {
      const data = line.startsWith("data: ") ? line.slice(6).trim() : "";
      if (!data || data === "[DONE]") continue;
      const chunk = JSON.parse(data) as {
        error?: unknown;
        usage?: { cost?: number };
        choices?: {
          delta?: {
            content?: string | null;
            reasoning?: string | null;
            tool_calls?: { index?: number; id?: string; function?: { name?: string; arguments?: string } }[] | null;
          };
        }[];
      };
      if (chunk.error) failed = true;
      if (typeof chunk.usage?.cost === "number") cost = Math.max(0, chunk.usage.cost);
      const delta = chunk.choices?.[0]?.delta;
      if (delta?.reasoning) now.thinking += delta.reasoning;
      if (delta?.content) now.content += delta.content;
      for (const piece of delta?.tool_calls ?? []) {
        const call = (calls[piece.index ?? calls.length] ??= {
          id: "",
          type: "function",
          function: { name: "", arguments: "" },
        });
        if (piece.id) call.id = piece.id;
        if (piece.function?.name) call.function.name += piece.function.name;
        if (piece.function?.arguments) call.function.arguments += piece.function.arguments;
      }
      if (delta?.reasoning || delta?.content) onProgress({ ...now });
    }
  }
  const made = calls.filter(Boolean).map((c, i) => ({ ...c, id: c.id || `call_${i}` }));
  if (failed || (!now.content && !made.length)) throw new AiError("failed");
  return { content: now.content, calls: made, cost };
}
