/**
 * The notebook document on the wire: the *.electro.json file format, version 2 (described in
 * full by Python's electro_notes). Checked here only as far as the server needs — its identity,
 * title and the shape of its cells; everything else (outputs, results, keys of newer versions)
 * passes through untouched, so no side loses data it does not understand.
 */
import { Schema } from "effect";

/** Keys a schema does not name: kept as they are. */
const Rest = Schema.Record({ key: Schema.String, value: Schema.Unknown });

/** A notebook's identity: stable across saves; also its address on the server. */
export const NoteId = Schema.String.pipe(
  Schema.pattern(/^[A-Za-z0-9_-]{1,64}$/),
  Schema.annotations({ identifier: "NoteId", description: "Identyfikator notatki (litery, cyfry, _ i -)" }),
);
export type NoteId = typeof NoteId.Type;

export const MarkdownCell = Schema.Struct(
  { id: Schema.NonEmptyString, type: Schema.Literal("markdown"), source: Schema.String },
  Rest,
);

export const CodeCell = Schema.Struct(
  { id: Schema.NonEmptyString, type: Schema.Literal("code"), source: Schema.String },
  Rest,
);

export const SchematicCell = Schema.Struct(
  {
    id: Schema.NonEmptyString,
    type: Schema.Literal("schematic"),
    name: Schema.NonEmptyString,
    schematic: Schema.Struct({ elements: Schema.Array(Schema.Unknown), wires: Schema.Array(Schema.Unknown) }, Rest),
  },
  Rest,
);

export const Cell = Schema.Union(MarkdownCell, CodeCell, SchematicCell);
export type Cell = typeof Cell.Type;

export const NotebookDocument = Schema.Struct(
  {
    format: Schema.Literal("electro-notebook"),
    version: Schema.Literal(2),
    id: NoteId,
    title: Schema.String,
    created: Schema.String,
    modified: Schema.String,
    settings: Schema.Struct({ codeInPdf: Schema.Boolean }, Rest),
    cells: Schema.Array(Cell),
  },
  Rest,
).annotations({ identifier: "NotebookDocument" });
export type NotebookDocument = typeof NotebookDocument.Type;

/**
 * The start of a note, enough to draw a thumbnail of its first page: the first few cells, cut
 * short (the server makes it when saving, so a list of notes needs no documents).
 */
export const PreviewCell = Schema.Union(
  Schema.Struct({ type: Schema.Literal("markdown"), source: Schema.String }),
  Schema.Struct({ type: Schema.Literal("code"), source: Schema.String }),
  Schema.Struct({
    type: Schema.Literal("schematic"),
    name: Schema.String,
    schematic: Schema.Struct({
      elements: Schema.Array(Schema.Unknown),
      wires: Schema.Array(Schema.Unknown),
      // one's own components on it: their outlines (what is inside them is not drawn)
      parts: Schema.optional(Schema.Record({ key: Schema.String, value: Schema.Unknown })),
    }),
  }),
);
export type PreviewCell = typeof PreviewCell.Type;

export const NotePreview = Schema.Struct({
  codeInPdf: Schema.Boolean, // the page shows code cells only when the PDF does
  cells: Schema.Array(PreviewCell),
}).annotations({ identifier: "NotePreview" });
export type NotePreview = typeof NotePreview.Type;
