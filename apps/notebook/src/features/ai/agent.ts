// The assistant as an agent: the conversation, the note and what was attached (pictures, a PDF's
// pages) go to the model with tools — to read the note, write text into it, draw a circuit (the solver
// checks it; drawn from a picture, the drawing comes back beside the picture's, to compare), look at
// a picture closer, work quantities out with the solver, remove cells — and it does with them whatever
// is asked: a note from a PDF, an answer about it, help with a problem, a change to the note. What a
// tool finds wrong goes back to it as the tool's result: it mends that itself. No tasks: a note is for
// notes (a test's tasks are its author's).
import { kernel } from "@/features/python";
import { fromDrawing, type Netlist, netlistOf } from "@/features/schematic/fromDrawing";
import { library } from "@/features/schematic/library";
import { pictureOf } from "@/features/schematic/picture";
import { newCell } from "@/shared/model/cells";
import type { Failure } from "@/shared/model/issues";
import type { Cell, SchematicData } from "@/shared/model/types";
import { textOf } from "./attachments";
import { type AiMessage, type AiTool, type AiToolCall, complete, type Progress } from "./client";
import { CIRCUIT_FORMAT, jsonOf } from "./protocol";

/** Calls of the model in one turn, at most (a 7-page PDF: 2 — its text and circuits at once, a look at them —
 *  and a mending or two). */
const MAX_STEPS = 40;
/** Times the agent draws a circuit in a turn, at most; a circuit drawn from a picture is mended against
 *  it this many rounds at most, on its own (a call of a few thousand tokens each). */
const DRAWS = 3;
const MENDS = 3;

type Content = Exclude<AiMessage["content"], null>;

const MEND = `You check a circuit redrawn from a document against the document. The picture: on the left the
document's circuit, on the right our drawing of the data given. Are they the same circuit — the same components
and values, each terminal joined to the same things — laid out the same way (places, directions, corners)?
The arrows of currents and voltages count too: each the picture marks there, by its name, the way it points,
by what it marks (its place more or less). Not to mind: the style, fonts, where labels stand, a ground symbol
we add, a value we leave unknown, dots at junctions, an open end's circle. Answer with ONE JSON object and nothing else: {"same": true} when
they are, else the data mended: {"same": false, "differences": ["...", ...], "elements": [...], "wires": [...]}.
${CIRCUIT_FORMAT}`;

const SYSTEM = `You are the assistant of "electro", a notebook for students of electrical engineering and electronics.

THE APP. A note is a list of cells: text (Markdown, formulas in $...$ LaTeX), circuits and Python code.
- A circuit cell is a drawing the solver works out: its run button (▶) gives every element's voltage, current
  and power on the drawing, and a step-by-step solution (Ohm's law, Kirchhoff's laws, series/parallel…), as
  on paper. An element's value may be left unknown (null): the solver finds it from what is given — other
  values, and meters' readings (an ammeter reading 2 A is the given I = 2 A in its branch). So a problem's
  circuit, drawn with all it gives (meters for the measured quantities) and its unknowns left null, is solved by
  the run button. Also AC (sine sources: phasors), Bode plots, a sweep of a value, a live simulation in time
  (switches, LEDs, transistors, logic, Arduino) — the user's to run.
- A code cell is Python with the "electro" library (elements by name, joined: E, R = VoltageSource("E"),
  Resistor("R_1"); Problem(loop(E, R), {E: 12, R: 10}); solve(problem)(I(R)) …). You do not write code cells.
You help with whatever the user asks: you answer questions, explain, help solve problems — step by step,
every number from the solve tool (the circuit's currents and voltages, which it knows; never a number you
worked out yourself) — and you write and change the note when asked to: a note from a photo or a PDF, a
summary, a circuit drawn, a mistake mended. Answers, explanations and solutions go in your reply (Markdown,
formulas in $...$), not into the note, unless the user asks for them there.

A NOTE FROM A DOCUMENT (a photo, a PDF): transcribe it as it is — its order, its headings (Markdown by rank:
the title "#", a section "##", a problem's or task's own "###"), its words exactly (a page's own text, when
given, is its exact words: use them, mending only what they garble, as formulas), nothing added, left out,
reworded, translated or solved; a blank to fill in as $R_2 = \\underline{\\qquad}\\,\\Omega$; one text cell per
heading. Each circuit right after the text it belongs to: a problem whose parts — a), b) — each have their
own circuit is split there: part a)'s text, its circuit, part b)'s text, its circuit. Every circuit drawn
(draw_circuit with its "source"), with what its problem gives — the statement it belongs to, which may stand
under a heading of its own before it (a "Task" whose circuit is the "Problem" above's): values the text gives
that the picture does not show on the elements, unknowns null. Its arrows of currents and voltages
(I_2 by R2, U_1 beside R1) drawn too, as the picture marks them, each "of" its element (a voltage between two
points: "between" them), with the value
the problem gives for it (I_2 = 2 A) — and an arrow for a given the picture has none for (the voltage
across R_5 = 125 V: a voltage arrow by R5), so the run button solves the problem. A drawing that is not a circuit, a page's
header or footer: left out. Do all of it — every page to its end.

Call the tools you can at once in one go (every circuit of a document together, say). A tool's result says
what is wrong, if anything: mend just that. A circuit drawn with its "source" is checked against the picture
and mended there on its own — what it says of it is final; tell the user of one that still differs.

Write in {LANGUAGE}, unless the document's own text is in another.

THE PICTURES (attached in this conversation, by number): {PICTURES}

THE NOTE NOW (cells in order, by id; new cells go after {AT} unless said otherwise):
{NOTE}`;

const where = {
  after: {
    type: "string",
    description: 'the id of the cell to put it after, or "start"/"end" (default: after the last one you added)',
  },
  replace: { type: "string", description: "the id of a cell to put this in place of (instead of a new one)" },
};

const TOOLS: AiTool[] = [
  {
    type: "function",
    function: {
      name: "read_note",
      description: "The note as it is now: its cells in order, each with its id (a circuit as its netlist).",
      parameters: { type: "object", properties: {} },
    },
  },
  {
    type: "function",
    function: {
      name: "write_text",
      description: "Writes a text cell (Markdown, formulas in $...$ LaTeX) into the note, or rewrites one.",
      parameters: {
        type: "object",
        properties: { markdown: { type: "string" }, ...where },
        required: ["markdown"],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "draw_circuit",
      description: `Draws a circuit into the note (or redraws one), checked by the solver: what is wrong comes back.
${CIRCUIT_FORMAT}
source: the picture it is drawn from and where on it (its whole drawing with its labels, a little margin):
it is checked against that part of the picture, and mended, before it comes back.`,
      parameters: {
        type: "object",
        properties: {
          name: { type: "string", description: 'a short name, e.g. the heading it is under ("Zadanie 3")' },
          elements: {
            type: "array",
            items: {
              type: "object",
              properties: {
                id: { type: "string" },
                kind: { type: "string" },
                value: { type: "string" },
                text: { type: "string" },
                of: { type: "string" },
                between: { type: "array", items: { type: "array", items: { type: "number" } } },
                flip: { type: "boolean" },
                nodes: { type: "array", items: { type: "string" } },
                at: { type: "array", items: { type: "array", items: { type: "number" } } },
              },
              required: ["id", "kind", "nodes", "at"],
            },
          },
          wires: { type: "array", items: { type: "array", items: { type: "array", items: { type: "number" } } } },
          source: {
            type: "object",
            properties: {
              picture: { type: "integer", description: "its number (from 1)" },
              box: {
                type: "array",
                items: { type: "number" },
                description: "[ymin, xmin, ymax, xmax], each 0–1000 of the picture's height and width",
              },
            },
          },
          ...where,
        },
        required: ["name", "elements", "wires"],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "look",
      description: "Shows a picture (a page) again, or a part of it closer (to read small labels).",
      parameters: {
        type: "object",
        properties: {
          picture: { type: "integer" },
          box: { type: "array", items: { type: "number" }, description: "[ymin, xmin, ymax, xmax], 0–1000" },
        },
        required: ["picture"],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "solve",
      description: `Works a circuit of the note out (its DC operating point): the solver knows how it is joined, so ask it
for the circuit's own currents and voltages — I_R1 (current through R1), U_R1 (voltage across it), P_R1 (its
power), V_A (potential of node A), I_E1, U_E1 (a source's) — not for a formula of yours (yours may join it
wrong). Each EXPR: those, an element's value (R1), + - * / ** ( ) sqrt abs. E.g. the total resistance seen by
a source E1: U_E1 / I_E1; a branch of R1 and R2 in series: (U_R1 + U_R2) / I_R1. Explain the steps with the
formulas, but take every number from here.`,
      parameters: {
        type: "object",
        properties: {
          circuit: { type: "string", description: "the circuit cell's id" },
          find: { type: "array", items: { type: "string" }, description: "EXPRs" },
        },
        required: ["circuit", "find"],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "remove_cells",
      description: "Removes cells from the note.",
      parameters: {
        type: "object",
        properties: { ids: { type: "array", items: { type: "string" } } },
        required: ["ids"],
      },
    },
  },
];

/** What the turn did, step by step, for the conversation to show. */
export type Doing = { tool: string; name?: string; issue?: string; done?: boolean };

type Box = [number, number, number, number];
const fits = (box: unknown): box is Box =>
  Array.isArray(box) &&
  box.length === 4 &&
  box.every((v) => typeof v === "number" && v >= 0 && v <= 1000) &&
  box[2] > box[0] &&
  box[3] > box[1];

const said = (f: Failure) => (f.issue ? JSON.stringify(f.issue) : f.data || "error");
const cut = (text: string, n: number) => (text.length > n ? `${text.slice(0, n)}…` : text);
const picture = (url: string) => ({ type: "image_url" as const, image_url: { url } });

// ------------------------------------------------------------------ pictures

const load = (url: string) =>
  new Promise<HTMLImageElement>((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error("the picture could not be read"));
    img.src = url;
  });

/** The part of a picture in ``box`` ([ymin, xmin, ymax, xmax], each 0–1000), a margin around it. */
async function crop(url: string, [y0, x0, y1, x1]: Box): Promise<string> {
  const img = await load(url);
  const m = 15; // (of 1000)
  const left = (Math.max(0, x0 - m) / 1000) * img.width;
  const top = (Math.max(0, y0 - m) / 1000) * img.height;
  const width = (Math.min(1000, x1 + m) / 1000) * img.width - left;
  const height = (Math.min(1000, y1 + m) / 1000) * img.height - top;
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(width));
  canvas.height = Math.max(1, Math.round(height));
  canvas.getContext("2d")!.drawImage(img, left, top, width, height, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL("image/jpeg", 0.9);
}

/** Two pictures side by side, the same height, on white: one picture for the model (half the tokens). */
async function beside(a: string, b: string): Promise<string> {
  const [x, y] = await Promise.all([load(a), load(b)]);
  const h = Math.min(500, Math.max(x.height, y.height));
  const wx = (x.width * h) / x.height;
  const wy = (y.width * h) / y.height;
  const gap = 24;
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(wx + gap + wy);
  canvas.height = h;
  const g = canvas.getContext("2d")!;
  g.fillStyle = "#fff";
  g.fillRect(0, 0, canvas.width, h);
  g.drawImage(x, 0, 0, wx, h);
  g.fillStyle = "#999";
  g.fillRect(wx + gap / 2 - 1, 0, 2, h);
  g.drawImage(y, wx + gap, 0, wy, h);
  return canvas.toDataURL("image/jpeg", 0.85);
}

/** An SVG drawing as a picture, black on white. */
async function rasterize(svg: string): Promise<string> {
  const dark = svg.replace("<svg ", '<svg style="color:#000" ');
  const img = await load(`data:image/svg+xml;charset=utf-8,${encodeURIComponent(dark)}`);
  const scale = Math.min(3, 1200 / Math.max(img.width, img.height, 1));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(img.width * scale);
  canvas.height = Math.round(img.height * scale);
  const g = canvas.getContext("2d")!;
  g.fillStyle = "#fff";
  g.fillRect(0, 0, canvas.width, canvas.height);
  g.drawImage(img, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL("image/png");
}

// ------------------------------------------------------------------ the note

/** The note as the model reads it: each cell's id, kind and what is in it (a circuit as a netlist). */
async function describe(cells: Cell[]): Promise<string> {
  if (!cells.length) return "(empty)";
  const lines: string[] = [];
  for (const c of cells) {
    if (c.type === "markdown") lines.push(`[${c.id}] text: ${JSON.stringify(cut(c.source, 1500))}`);
    else if (c.type === "code") lines.push(`[${c.id}] code (Python): ${JSON.stringify(cut(c.source, 600))}`);
    else {
      let read: string;
      try {
        read = JSON.stringify(netlistOf(c.schematic, library).elements);
      } catch {
        read = "(cannot be read)";
      }
      lines.push(`[${c.id}] circuit "${c.name}": ${read}`);
    }
  }
  return lines.join("\n");
}

/** A conversation's earlier turns, sent again: their pictures as words (the look tool shows them). */
const plain = (m: AiMessage): AiMessage =>
  m.content === null || typeof m.content === "string"
    ? m
    : ({
        ...m,
        content: m.content.map((p) => (p.type === "text" ? p : { type: "text" as const, text: "(a picture)" })),
      } as AiMessage);

// ------------------------------------------------------------------ the turn

export interface TurnResult {
  message: string;
  cells: Cell[];
  added: number;
  changed: number;
  history: AiMessage[]; // the conversation after it (to go on from)
  cost: number; // what the model cost (dollars, as OpenRouter says)
}

/** One turn of the conversation: ``asked`` (with the pictures newly attached) done with the tools, the
 *  note changed as it goes (``onCells``), what is being done said (``onDoing``, ``onProgress``). */
export async function turn({
  asked,
  attached,
  pictures,
  history,
  cells: start,
  at,
  language,
  onCells,
  onDoing,
  onProgress,
}: {
  asked: string;
  attached: number[]; // which of ``pictures`` came with this request (their numbers, from 1)
  pictures: string[]; // every picture of the conversation
  history: AiMessage[];
  cells: Cell[];
  at: number;
  language: string;
  onCells: (cells: Cell[]) => void;
  onDoing: (doing: Doing[]) => void;
  onProgress: (now: Progress | null) => void;
}): Promise<TurnResult> {
  await kernel.ready;
  let cells = [...start];
  let cursor = at; // where the next new cell goes
  let cost = 0;
  const fresh = new Set<string>();
  const drawsOf = new Map<string, number>(); // a circuit's draws, by its cell (or, not drawn yet, its name)
  const changed = new Set<string>();
  const doing: Doing[] = [];
  const show = () => onDoing(doing.map((d) => ({ ...d })));
  const set = (next: Cell[]) => {
    cells = next;
    onCells(cells);
  };
  /** A cell into the note: in place of ``replace``, after ``after``, or where the last one went. */
  const put = (cell: Cell, { after, replace }: { after?: string; replace?: string }): string | null => {
    if (replace) {
      const i = cells.findIndex((c) => c.id === replace);
      if (i < 0) return `no cell ${replace} in the note`;
      const next = { ...cells[i]!, ...cell, id: replace } as Cell;
      if (!fresh.has(replace)) changed.add(replace);
      set(cells.map((c, k) => (k === i ? next : c)));
      return null;
    }
    if (after === "start") cursor = 0;
    else if (after === "end") cursor = cells.length;
    else if (after) {
      // (one not in the note — an id the model made up for a cell of the same batch: in order, as it goes)
      const i = cells.findIndex((c) => c.id === after);
      if (i >= 0) cursor = i + 1;
    }
    cursor = Math.min(cursor, cells.length);
    set([...cells.slice(0, cursor), cell, ...cells.slice(cursor)]);
    cursor++;
    fresh.add(cell.id);
    return null;
  };

  /** The solver's drawing of a circuit's data: as drawn, or what is wrong (and it laid out by its nodes). */
  const drawing = async (
    data: Netlist,
  ): Promise<{ schematic: SchematicData } | { why: string[]; fallback?: SchematicData }> => {
    const missing = data.elements.filter((e) => !Array.isArray(e.at)).map((e) => e.id);
    if (!data.elements.length) return { why: ["no elements"] };
    if (missing.length) return { why: [`no "at" for ${missing.join(", ")}: where its terminals are drawn`] };
    const drawn = fromDrawing(data, library, true);
    if (!("error" in drawn)) return { schematic: drawn.schematic };
    const e = drawn.error;
    const anew = fromDrawing(data, library, false);
    return {
      why: e.mismatch ?? e.dangling ?? [said(e)],
      ...(!("error" in anew) ? { fallback: anew.schematic } : {}),
    };
  };

  /** A circuit drawn from a picture, checked against it and mended, in a conversation of its own (the
   *  cut-out and ours side by side, its data — a few thousand tokens, not the whole turn's): what the
   *  agent is told of it. */
  const mend = async ({
    id,
    name,
    theirs,
    data,
    schematic,
    why,
    step,
  }: {
    id: string;
    name: string;
    theirs: string;
    data: Netlist;
    schematic: SchematicData;
    why: string[];
    step: Doing;
  }): Promise<Content> => {
    const shown = async (s: SchematicData) =>
      picture(await beside(theirs, await rasterize(await pictureOf(s, library))));
    const talk: AiMessage[] = [
      { role: "system", content: MEND },
      {
        role: "user",
        content: [
          {
            type: "text",
            text: `The data: ${JSON.stringify(data)}${why.length ? `\nThe solver: it does not hold — ${why.join("; ")} (drawn laid out by its nodes meanwhile)` : ""}`,
          },
          await shown(schematic),
        ],
      },
    ];
    let left: string[] = why;
    for (let round = 0; round < MENDS; round++) {
      const answer = await complete(talk).catch(() => null);
      if (!answer) break;
      cost += answer.cost;
      let reply: { same?: boolean; differences?: string[] } & Partial<Netlist>;
      try {
        reply = jsonOf(answer.content);
      } catch {
        break;
      }
      if (reply.same && !left.length) {
        left = [];
        break;
      }
      left = reply.differences?.length ? reply.differences : left;
      step.issue = left[0];
      show();
      talk.push({ role: "assistant", content: answer.content });
      if (!reply.elements?.length) {
        talk.push({
          role: "user",
          content: "Answer with the data mended (elements and wires), the whole JSON object.",
        });
        continue;
      }
      const got = await drawing({ elements: reply.elements, wires: reply.wires ?? [] });
      if ("why" in got) {
        left = got.why;
        talk.push({ role: "user", content: `The solver: it does not hold — ${got.why.join("; ")}. Mend it.` });
        continue;
      }
      put({ ...newCell("schematic"), type: "schematic", name, schematic: got.schematic } as Cell, { replace: id });
      left = [];
      talk.push({
        role: "user",
        content: [{ type: "text", text: "Drawn anew — now?" }, await shown(got.schematic)],
      });
    }
    step.done = true;
    step.issue = left[0];
    show();
    return left.length
      ? `ok: drawn as cell ${id}, but it still differs from the picture: ${left.join("; ")}`
      : `ok: drawn as cell ${id}, checked against the picture`;
  };

  /** A tool run: what goes back to the model — or, for what takes longer (a circuit checked against its
   *  picture), how to get it, run beside the others' once the batch is in place. */
  const run = async (call: AiToolCall): Promise<Content | (() => Promise<Content>)> => {
    let args: Record<string, unknown>;
    try {
      args = jsonOf<Record<string, unknown>>(call.function.arguments || "{}");
    } catch {
      return "error: the arguments are not one JSON object";
    }
    const str = (v: unknown) => (typeof v === "string" && v ? v : undefined);
    const place = { after: str(args.after), replace: str(args.replace) };
    switch (call.function.name) {
      case "read_note":
        return describe(cells);
      case "write_text": {
        // a cell a heading (the text split before each one)
        const parts = String(args.markdown ?? "")
          .split(/\n(?=#{1,6}\s)/)
          .map((p) => p.trim())
          .filter(Boolean);
        if (!parts.length) return "error: no markdown";
        const ids: string[] = [];
        for (const [k, source] of parts.entries()) {
          const cell = { ...newCell("markdown"), type: "markdown", source } as Cell;
          const wrong = put(cell, k === 0 ? place : { after: ids.at(-1) });
          if (wrong) return `error: ${wrong}`;
          ids.push(k === 0 && place.replace ? place.replace : cell.id);
        }
        return `ok: ${ids.length > 1 ? "cells" : "cell"} ${ids.join(", ")}`;
      }
      case "draw_circuit": {
        const elements = (Array.isArray(args.elements) ? args.elements : []) as Netlist["elements"];
        const wires = (Array.isArray(args.wires) ? args.wires : []) as Netlist["wires"];
        const name = str(args.name) ?? "Układ";
        const step: Doing = { tool: "draw_circuit", name };
        doing.push(step);
        show();
        const tries = (drawsOf.get(place.replace ?? name) ?? 0) + 1;
        if (tries > DRAWS) return `error: drawn ${DRAWS} times already — leave it as it is and go on`;
        drawsOf.set(place.replace ?? name, tries);
        // not drawn: where it was to go, for its next go (the cells after it go on being written)
        const again = place.replace
          ? `replace: "${place.replace}"`
          : `after: "${place.after ?? cells[Math.min(cursor, cells.length) - 1]?.id ?? "start"}"`;
        const refuse = (why: string[]) => {
          step.issue = why[0];
          show();
          return `error — not drawn; mend this and call draw_circuit again (with ${again}), redoing nothing else:\n- ${why.join("\n- ")}`;
        };
        const source = args.source as { picture?: number; box?: unknown } | undefined;
        const url = source?.picture ? pictures[source.picture - 1] : undefined;
        const got = await drawing({ elements, wires });
        // drawn from a picture: in as it is (laid out by its nodes, if need be), then checked against the
        // picture and mended there — on its own, beside the others (see ``mend``)
        const schematic = "schematic" in got ? got.schematic : url ? got.fallback : undefined;
        if (!schematic) return refuse("why" in got ? got.why : ["the solver could not read it"]);
        const cell = { ...newCell("schematic"), type: "schematic", name, schematic } as Cell;
        const wrong = put(cell, place);
        if (wrong) return `error: ${wrong}`;
        const id = place.replace ?? cell.id;
        drawsOf.set(id, tries);
        if (!url) {
          step.done = true;
          show();
          return `ok: drawn as cell ${id}`;
        }
        const theirs = fits(source!.box) ? await crop(url, source!.box) : url;
        return () =>
          mend({ id, name, theirs, data: { elements, wires }, schematic, why: "why" in got ? got.why : [], step });
      }
      case "look": {
        const url = pictures[Number(args.picture) - 1];
        if (!url) return `error: no picture ${String(args.picture)} (there are ${pictures.length})`;
        return [
          { type: "text", text: `picture ${String(args.picture)}:` },
          picture(fits(args.box) ? await crop(url, args.box) : url),
        ];
      }
      case "solve": {
        const cell = cells.find((c) => c.id === args.circuit);
        if (cell?.type !== "schematic") return `error: no circuit ${String(args.circuit)} in the note`;
        const find = (Array.isArray(args.find) ? args.find : []).map(String);
        const steps = find.map((value, k) => ({ id: `q${k}`, label: value, unit: "", value }));
        const got = await kernel.taskValues(cell.schematic, steps).catch(() => null);
        if (!got) return "error: the solver could not work it out";
        if ("error" in got) return `error: ${said(got.error)}`;
        return find
          .map((expr, k) => {
            const v = got.values[`q${k}`];
            return `${expr} = ${!v ? "?" : "error" in v ? `error: ${said(v.error)}` : String(v.value)}`;
          })
          .join("\n");
      }
      case "remove_cells": {
        const ids = new Set((Array.isArray(args.ids) ? args.ids : []).map(String));
        const gone = cells.filter((c) => ids.has(c.id)).length;
        set(cells.filter((c) => !ids.has(c.id)));
        for (const id of ids) if (!fresh.delete(id)) changed.add(id);
        return `ok: ${gone} removed`;
      }
      default:
        return `error: no tool ${call.function.name}`;
    }
  };

  const system: AiMessage = {
    role: "system",
    content: SYSTEM.replace("{LANGUAGE}", language === "en" ? "English" : "Polish")
      .replace("{PICTURES}", pictures.length ? `1–${pictures.length}` : "none")
      .replace("{AT}", at > 0 && start[at - 1] ? `cell ${start[at - 1]!.id}` : "the start")
      .replace("{NOTE}", await describe(start)),
  };
  const request: AiMessage = {
    role: "user",
    content: [
      { type: "text", text: asked.trim() || (attached.length ? "Make a note of this." : "") },
      ...attached.flatMap((n) => {
        const text = textOf.get(pictures[n - 1]!);
        return [
          { type: "text" as const, text: `Picture ${n}${text ? ` — its own text: ${JSON.stringify(text)}` : ""}` },
          picture(pictures[n - 1]!),
        ];
      }),
    ],
  };
  // the conversation so far (its pictures as words), its newest turns (a bound on what is sent)
  const earlier = history.map(plain).slice(-200);
  const first = earlier.findIndex((m) => m.role === "user");
  const messages: AiMessage[] = [...(first < 0 ? [] : earlier.slice(first)), request];
  let message = "";
  let seenUpTo = 0; // tools' results before it: seen (their pictures sent once — each costs ~1.4k tokens a call)
  for (let step = 0; step < MAX_STEPS; step++) {
    const sent = messages.map((m, i) => (i < seenUpTo && m.role === "tool" ? plain(m) : m));
    seenUpTo = messages.length;
    const answer = await complete([system, ...sent], TOOLS, onProgress);
    onProgress(null);
    cost += answer.cost;
    messages.push({
      role: "assistant",
      content: answer.content || null,
      ...(answer.calls.length ? { tool_calls: answer.calls } : {}),
    });
    if (!answer.calls.length) {
      message = answer.content;
      break;
    }
    const results: (Content | (() => Promise<Content>))[] = [];
    for (const call of answer.calls) {
      if (call.function.name !== "draw_circuit") {
        doing.push({ tool: call.function.name });
        show();
      }
      results.push(await run(call).catch((e: unknown) => `error: ${e instanceof Error ? e.message : String(e)}`));
      if (call.function.name !== "draw_circuit") doing.at(-1)!.done = true;
    }
    // what takes longer, beside each other
    const contents = await Promise.all(
      results.map((r) => (typeof r === "function" ? r().catch(() => "ok: drawn, not checked") : r)),
    );
    for (const [k, call] of answer.calls.entries())
      messages.push({ role: "tool", tool_call_id: call.id, content: contents[k]! });
    show();
  }
  return {
    message,
    cells,
    added: [...fresh].filter((id) => cells.some((c) => c.id === id)).length,
    changed: changed.size,
    history: [...earlier, ...messages.slice(messages.indexOf(request))],
    cost,
  };
}
