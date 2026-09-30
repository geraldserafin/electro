// What the user may do with a card, as the server decides it (LibraryRepo): the page only hides
// what would be refused.
import { type ItemCard, RANK, type Role } from "@electro/notes-api";

/** Change it: rename it, write in it, put things into it (a folder). */
export const canEdit = (card: ItemCard) => RANK[card.role] >= RANK.editor;

/** Take it out of where it is (delete it, move it away): its owner, or an editor of the folder it
 *  is in (``container``: the user's role there; null — the top of the home screen). */
export const canTakeOut = (card: ItemCard, container: Role | null) =>
  card.owner === null || (container !== null && RANK[container] >= RANK.editor);
