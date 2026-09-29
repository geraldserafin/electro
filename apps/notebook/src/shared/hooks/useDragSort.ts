// Dragging an item of a list to a new place, by a handle (the pointer, not HTML drag and drop:
// it works the same with a mouse, a pen and a finger). While dragged, a line shows where it
// would land: before one of the items, or after the last.
import { useRef, useState, type PointerEvent } from "react";

export interface DropLine { top: number; left: number; width: number }

export function useDragSort({ items, onDrop }: {
  items: () => HTMLElement[]; // the list's items as they are on screen, in order
  onDrop: (before: number) => void; // where it was let go: before items()[before] (length: after the last)
}) {
  const [line, setLine] = useState<DropLine | null>(null);
  const before = useRef<number | null>(null);

  const place = (y: number) => {
    const boxes = items().map((el) => el.getBoundingClientRect());
    if (!boxes.length) return;
    const at = boxes.filter((b) => b.top + b.height / 2 < y).length;
    before.current = at;
    const top = at < boxes.length ? boxes[at].top - 3 : boxes[boxes.length - 1].bottom + 3;
    const { left, width } = boxes[Math.min(at, boxes.length - 1)];
    setLine({ top, left, width });
  };

  const end = (drop: boolean) => {
    if (drop && before.current !== null) onDrop(before.current);
    before.current = null;
    setLine(null);
  };

  return {
    dragging: line !== null,
    line,
    /** For the handle's element. */
    handle: {
      onPointerDown: (event: PointerEvent<HTMLElement>) => {
        if (event.button !== 0) return;
        event.preventDefault();
        event.currentTarget.setPointerCapture(event.pointerId);
        place(event.clientY);
      },
      onPointerMove: (event: PointerEvent<HTMLElement>) => {
        if (event.currentTarget.hasPointerCapture(event.pointerId)) place(event.clientY);
      },
      onPointerUp: () => end(true),
      onPointerCancel: () => end(false),
    },
  };
}
