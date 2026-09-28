// Who is signed in, as atoms on the notes client: the user (Unauthorized: no one), the providers
// the server can sign in with, and signing out.
import { NotesClient } from "@/features/notes";

export const meAtom = NotesClient.query("auth", "me", {});
export const providersAtom = NotesClient.query("auth", "providers", {});
export const logout = NotesClient.mutation("auth", "logout");
