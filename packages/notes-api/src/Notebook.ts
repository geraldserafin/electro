/**
 * The notebook document on the wire: the *.electro.json file format, version 2 (described in
 * full by Python's electro_notes). Checked here only as far as the server needs — its identity,
 * title and the shape of its cells; everything else (outputs, results, keys of newer versions)
 * passes through untouched, so no side loses data it does not understand.
 */
import { Schema } from "effect"

/** Keys a schema does not name: kept as they are. */
const Rest = Schema.Record({ key: Schema.String, value: Schema.Unknown })

/** A notebook's identity: stable across saves; also its address on the server. */
export const NoteId = Schema.String.pipe(
  Schema.pattern(/^[A-Za-z0-9_-]{1,64}$/),
  Schema.annotations({ identifier: "NoteId", description: "Identyfikator notatki (litery, cyfry, _ i -)" }),
)
export type NoteId = typeof NoteId.Type

export const MarkdownCell = Schema.Struct(
  { id: Schema.NonEmptyString, type: Schema.Literal("markdown"), source: Schema.String },
  Rest,
)

export const CodeCell = Schema.Struct(
  { id: Schema.NonEmptyString, type: Schema.Literal("code"), source: Schema.String },
  Rest,
)

export const SchematicCell = Schema.Struct(
  {
    id: Schema.NonEmptyString,
    type: Schema.Literal("schematic"),
    name: Schema.NonEmptyString,
    schematic: Schema.Struct({ elements: Schema.Array(Schema.Unknown), wires: Schema.Array(Schema.Unknown) }, Rest),
  },
  Rest,
)

export const Cell = Schema.Union(MarkdownCell, CodeCell, SchematicCell)
export type Cell = typeof Cell.Type

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
).annotations({ identifier: "NotebookDocument" })
export type NotebookDocument = typeof NotebookDocument.Type

/** What a list of notes shows, without the documents themselves. */
export const NoteSummary = Schema.Struct({
  id: NoteId,
  title: Schema.String,
  modified: Schema.String, // as the notebook says (when it was last edited)
  savedAt: Schema.String, // when the server stored this revision
  revision: Schema.Int,
  cells: Schema.Int,
  schematics: Schema.Int,
}).annotations({ identifier: "NoteSummary" })
export type NoteSummary = typeof NoteSummary.Type

/** A stored note: the document and its revision (for saving without overwriting newer work). */
export const Note = Schema.Struct({
  document: NotebookDocument,
  revision: Schema.Int,
  savedAt: Schema.String,
}).annotations({ identifier: "Note" })
export type Note = typeof Note.Type

/**
 * Saving: the revision the client started from — ``null`` for a note the server does not have
 * yet. Anything else than the stored revision is a conflict (someone saved in between).
 */
export const SaveNote = Schema.Struct({
  document: NotebookDocument,
  baseRevision: Schema.NullOr(Schema.Int),
}).annotations({ identifier: "SaveNote" })
export type SaveNote = typeof SaveNote.Type

export const Saved = Schema.Struct({ revision: Schema.Int, savedAt: Schema.String })
export type Saved = typeof Saved.Type
