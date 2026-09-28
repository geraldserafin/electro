// The card being dragged (one at a time, on one page): what a folder asks when something is
// dragged over it.
import type { ItemCard } from "@electro/notes-api";

let current: ItemCard | null = null;

export const dragging = {
  get: () => current,
  start: (card: ItemCard) => { current = card; },
  end: () => { current = null; },
};
