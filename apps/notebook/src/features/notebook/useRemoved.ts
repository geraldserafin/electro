// Cells removed from the note, to take back: Ctrl/⌘ Z brings the last one back where it was (unless
// the keyboard is in a field, the code or a board — they undo their own), and so on back; a note
// of the last removal shows a moment, with the same "undo" on it.
import { useCallback, useEffect, useRef, useState } from "react";
import type { Cell } from "@/shared/model/types";

const SHOWN = 6000; // ms the note of a removal stays

export function useRemoved(cells: () => Cell[], setCells: (fn: (cells: Cell[]) => Cell[]) => void) {
  const stack = useRef<{ cell: Cell; index: number }[]>([]);
  const [last, setLast] = useState<Cell | null>(null); // the note shown: what was removed last
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);

  const show = (cell: Cell | null) => {
    clearTimeout(timer.current);
    setLast(cell);
    if (cell) timer.current = setTimeout(() => setLast(null), SHOWN);
  };

  const remove = (id: string) => {
    const index = cells().findIndex((c) => c.id === id);
    if (index < 0) return;
    const cell = cells()[index];
    stack.current.push({ cell, index });
    show(cell);
    setCells((all) => all.filter((c) => c.id !== id));
  };

  const undo = useCallback(() => {
    const removed = stack.current.pop();
    if (!removed) return false;
    setCells((cells) => [...cells.slice(0, removed.index), removed.cell, ...cells.slice(removed.index)]);
    show(stack.current.at(-1)?.cell ?? null);
    return true;
  }, [setCells]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!(e.metaKey || e.ctrlKey) || e.shiftKey || e.key.toLowerCase() !== "z" || e.defaultPrevented) return;
      const target = e.target as HTMLElement | null;
      if (target?.closest("input, textarea, [contenteditable], .cm-editor, [data-board]")) return; // their own undo
      if (undo()) e.preventDefault();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [undo]);
  useEffect(() => () => clearTimeout(timer.current), []);

  return { remove, undo, last, dismiss: () => show(null) };
}
