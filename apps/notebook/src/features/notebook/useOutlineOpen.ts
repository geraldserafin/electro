import { useState } from "react";

const KEY = "electro-outline";

/** Is the table of contents open: as last left in this browser; at first, on wide screens. */
export function useOutlineOpen(): [boolean, (open: boolean) => void] {
  const [open, setOpen] = useState(() => {
    try {
      const saved = localStorage.getItem(KEY);
      if (saved !== null) return saved === "1";
    } catch {
      // no storage: the default
    }
    return window.innerWidth >= 1200;
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
