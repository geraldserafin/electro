// Where the note sits: a column in the middle, beside the sidebar while that is open (on narrow
// screens the sidebar covers the note instead). Shared with the skeleton shown while it loads.
const ease = "ease-[cubic-bezier(0.2,0.8,0.2,1)] duration-250 motion-reduce:transition-none";

export const column = (withSidebar: boolean) =>
  `mx-auto max-w-280 px-6 max-sm:px-3 pt-18 pb-30 transition-[padding-left,max-width] ${ease} ` +
  (withSidebar ? "min-[901px]:max-w-[calc(1120px+312px)] min-[901px]:pl-[calc(24px+312px)]" : "");

/** Where the sidebar covers the note instead of standing beside it. */
export const NARROW = "(max-width: 900px)";

export const sidebar = (open: boolean) =>
  `fixed top-17 left-3 bottom-3 z-20 w-75 max-sm:right-3 max-sm:w-auto flex flex-col p-1 overflow-hidden rounded-xl border border-line bg-surface ` +
  `transition-[opacity,translate,visibility] ${ease} ` +
  (open ? "" : "invisible opacity-0 -translate-x-3");
