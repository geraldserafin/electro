import { type RefObject, useEffect } from "react";

/** While ``active``: a press anywhere outside ``ref`` calls ``onOutside`` (a menu closes, say). */
export function useClickOutside(ref: RefObject<HTMLElement | null>, active: boolean, onOutside: () => void) {
  useEffect(() => {
    if (!active) return;
    const press = (event: PointerEvent) => {
      if (!ref.current?.contains(event.target as Node)) onOutside();
    };
    document.addEventListener("pointerdown", press);
    return () => document.removeEventListener("pointerdown", press);
  }, [ref, active, onOutside]);
}
