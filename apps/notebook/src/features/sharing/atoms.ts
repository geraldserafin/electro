// Sharing on the notes server: who has an item, and changing that (each call answers with who has
// it now); leaving what was shared; opening a link. What changes a card ("shared", or the card
// itself) refreshes the library.
import { NotesClient } from "@/features/notes";

export const getSharing = NotesClient.mutation("sharing", "get");
export const addPerson = NotesClient.mutation("sharing", "add");
export const setRole = NotesClient.mutation("sharing", "setRole");
export const unshare = NotesClient.mutation("sharing", "unshare");
export const setLink = NotesClient.mutation("sharing", "link");
export const newLink = NotesClient.mutation("sharing", "newLink");
export const unlink = NotesClient.mutation("sharing", "unlink");
export const leave = NotesClient.mutation("sharing", "leave");
export const join = NotesClient.mutation("sharing", "join");

/** The address a link's token makes. */
export const joinUrl = (token: string) => `${location.origin}/join/${token}`;
