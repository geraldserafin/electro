export { join, joinUrl, leave } from "./atoms";
export * as messages from "./messages";
export { ShareDialog, type Shared } from "./ShareDialog";

/** Sharing is off: the notes are in each user's own vault on GitHub (features/vault), which shares nothing yet. */
export const enabled = false;
