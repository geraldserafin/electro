// Dragging an item of a list to a new place, by a handle (the pointer, not HTML drag and drop:
// it works the same with a mouse, a pen and a finger). While dragged, a line shows where it
// would land: before one of the items, or after the last. With a ``threshold`` the handle is the
// item itself: a press is still a click until it moves that far.
import { type MouseEvent, type PointerEvent, useRef, useState } from "react";

export interface DropLine {
  top: number;
  left: number;
  width: number;
}

export function useDragSort({
  items,
  onDrop,
  threshold = 0,
}: {
  items: () => HTMLElement[]; // the list's items as they are on screen, in order
  onDrop: (before: number) => void; // where it was let go: before items()[before] (length: after the last)
  threshold?: number; // px the pointer moves before it drags
}) {
  const [line, setLine] = useState<DropLine | null>(null);
  const before = useRef<number | null>(null);
  const dragged = useRef(false); // the click that ends a drag is not one

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
        dragged.current = false;
        if (threshold) {
          // a press, until the pointer goes that far (wherever it is by then: it may have left the item)
          const el = event.currentTarget;
          const { pointerId, clientY } = event;
          const move = (e: globalThis.PointerEvent) => {
            if (Math.abs(e.clientY - clientY) < threshold) return;
            stop();
            dragged.current = true;
            el.setPointerCapture(pointerId);
            place(e.clientY);
          };
          const stop = () => {
            window.removeEventListener("pointermove", move);
            window.removeEventListener("pointerup", stop);
            window.removeEventListener("pointercancel", stop);
          };
          window.addEventListener("pointermove", move);
          window.addEventListener("pointerup", stop);
          window.addEventListener("pointercancel", stop);
          return;
        }
        event.preventDefault();
        event.currentTarget.setPointerCapture(event.pointerId);
        place(event.clientY);
      },
      onPointerMove: (event: PointerEvent<HTMLElement>) => {
        if (event.currentTarget.hasPointerCapture(event.pointerId)) place(event.clientY);
      },
      onPointerUp: () => end(true),
      onPointerCancel: () => end(false),
      onClickCapture: (event: MouseEvent<HTMLElement>) => {
        if (!dragged.current) return;
        dragged.current = false;
        event.preventDefault();
        event.stopPropagation();
      },
    },
  };
}
