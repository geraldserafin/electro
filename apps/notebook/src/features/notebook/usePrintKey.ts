import { useEffect } from "react";

/** Ctrl+P (⌘P) calls ``onPrint`` instead of printing the page (the PDF is set by Typst). */
export function usePrintKey(onPrint: () => void) {
  useEffect(() => {
    const press = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && !e.altKey && e.key.toLowerCase() === "p") {
        e.preventDefault();
        onPrint();
      }
    };
    window.addEventListener("keydown", press);
    return () => window.removeEventListener("keydown", press);
  }, [onPrint]);
}
