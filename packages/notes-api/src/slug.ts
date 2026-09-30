/**
 * A note's address from its title: "Zadanie 4 — mostek Wheatstone'a" → "zadanie-4-mostek-wheatstonea".
 * The server makes it unique (a -2, -3… suffix) and keeps old ones working.
 */
const LETTERS: Record<string, string> = { ł: "l", Ł: "l", ß: "ss", æ: "ae", ø: "o", đ: "d" };

export const slugify = (title: string): string => {
  const slug = title
    .replace(/[łŁßæøđ]/g, (c) => LETTERS[c] ?? c)
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "") // ą → a, ó → o, …
    .toLowerCase()
    .replace(/['’]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 60)
    .replace(/-+$/, "");
  return slug || "notatka";
};
