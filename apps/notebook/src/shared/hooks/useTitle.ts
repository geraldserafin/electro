import { useEffect } from "react";

/** The browser tab's title: the page's own, then the app's ("Prawo Ohma · Electro Notebook"); none: the app's. */
export function useTitle(title?: string | null) {
  useEffect(() => {
    document.title = title?.trim() ? `${title.trim()} · Electro Notebook` : "Electro Notebook";
  }, [title]);
}
