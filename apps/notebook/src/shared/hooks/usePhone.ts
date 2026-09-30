import { useSyncExternalStore } from "react";

/** A phone's width (Tailwind's max-sm): where the page is laid out for one narrow column. */
export const PHONE = "(max-width: 639px)";

const query = typeof matchMedia === "undefined" ? null : matchMedia(PHONE);
const subscribe = (changed: () => void) => {
  query?.addEventListener("change", changed);
  return () => query?.removeEventListener("change", changed);
};

/** Whether the window is a phone's width now (and again when it changes: turned, resized). */
export function usePhone(): boolean {
  return useSyncExternalStore(subscribe, () => query?.matches ?? false);
}
