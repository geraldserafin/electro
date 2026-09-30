import { useState } from "react";
import { NARROW } from "./layout";

const KEY = "electro-outline";

/** Is the table of contents open: as last left in this browser; at first, closed. */
export function useOutlineOpen(): [boolean, (open: boolean) => void] {
  const [open, setOpen] = useState(() => {
    try {
      const saved = localStorage.getItem(KEY);
      if (matchMedia(NARROW).matches) return false; // (where it covers the note: it opens when asked)
      if (saved !== null) return saved === "1";
    } catch {
      // no storage: the default
    }
    return false;
  });
  const set = (next: boolean) => {
    setOpen(next);
    try {
      localStorage.setItem(KEY, next ? "1" : "0");
    } catch {
      // not remembered — fine
    }
  };
  return [open, set];
}
