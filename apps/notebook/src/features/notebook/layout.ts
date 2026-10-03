// Where the note sits: a column in the middle, beside the sidebar while that is open (on narrow
// screens the sidebar covers the note instead, an island; beside it, it lies on the page itself).
// Shared with the skeleton shown while it loads.
const ease = "ease-[cubic-bezier(0.2,0.8,0.2,1)] duration-250 motion-reduce:transition-none";

export const column = (withSidebar: boolean, withChat = false) =>
  `mx-auto max-w-280 px-6 max-sm:px-3 pt-18 pb-30 transition-[padding-left,padding-right,max-width] ${ease} ` +
  (withSidebar && withChat
    ? "min-[1301px]:max-w-[calc(1120px+252px+412px)] min-[1301px]:pl-[calc(24px+252px)] min-[1301px]:pr-[calc(24px+412px)]"
    : withSidebar
      ? "min-[901px]:max-w-[calc(1120px+252px)] min-[901px]:pl-[calc(24px+252px)]"
      : withChat
        ? "min-[901px]:max-w-[calc(1120px+412px)] min-[901px]:pr-[calc(24px+412px)]"
        : "");

/** Where the sidebar covers the note instead of standing beside it. */
export const NARROW = "(max-width: 900px)";

export const sidebar = (open: boolean) =>
  `fixed top-24 max-[900px]:top-17 left-3 bottom-3 z-20 w-60 max-sm:right-3 max-sm:w-auto flex flex-col p-1 overflow-hidden ` +
  `max-[900px]:rounded-xl max-[900px]:border max-[900px]:border-line max-[900px]:bg-surface max-[900px]:shadow-menu ` +
  `transition-[opacity,translate,visibility] ${ease} ` +
  (open ? "" : "invisible opacity-0 -translate-x-3");
