/** The start of a note for its thumbnail: what fits on (about) the first page, cut short. */
import type { NotebookDocument, NotePreview, PreviewCell } from "@electro/notes-api"

const CELLS = 8 // at most this many cells
const TEXT = 1600 // characters of text in all
const CODE_LINES = 12
const SCHEMATICS = 2

export const preview = (document: NotebookDocument): NotePreview => {
  const codeInPdf = document.settings.codeInPdf
  const cells: PreviewCell[] = []
  let text = 0
  let schematics = 0
  for (const cell of document.cells) {
    if (cells.length >= CELLS || text >= TEXT) break
    if (cell.type === "markdown") {
      const source = cell.source.slice(0, TEXT - text)
      text += source.length
      cells.push({ type: "markdown", source })
    } else if (cell.type === "code") {
      if (!codeInPdf) continue // not on the page
      const source = cell.source.split("\n").slice(0, CODE_LINES).join("\n")
      text += source.length
      cells.push({ type: "code", source })
    } else if (schematics < SCHEMATICS) {
      schematics++
      cells.push({
        type: "schematic",
        name: cell.name,
        schematic: { elements: cell.schematic.elements, wires: cell.schematic.wires },
      })
    }
  }
  return { codeInPdf, cells }
}
