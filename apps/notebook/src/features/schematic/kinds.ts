// The element kinds with their names in the app's language, and the library's search over them.
import { useTranslation } from "react-i18next";
import { KINDS, type KindGroup, type KindInfo } from "./model";

export type NamedKind = KindInfo & { name: string; words: string; groupName: string };

/** Case- and accent-insensitive: "zrodlo" finds "Źródło napięcia". */
export const plain = (text: string) => text.normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/ł/g, "l").toLowerCase();

export function useKinds() {
  const { t } = useTranslation("schematic");
  const kinds: NamedKind[] = KINDS.map((k) => ({
    ...k, name: t(`kinds.${k.kind}.name`), words: t(`kinds.${k.kind}.words`), groupName: t(`groups.${k.group as KindGroup}`),
  }));
  return {
    kinds,
    /** A kind's name ("Rezystor"), or the kind itself for one the library does not know. */
    name: (kind: string) => kinds.find((k) => k.kind === kind)?.name ?? kind,
    /** The kinds whose name, other names or group have ``query`` in them. */
    search: (query: string) => {
      const q = plain(query.trim());
      return q ? kinds.filter((k) => plain(`${k.name} ${k.words} ${k.groupName}`).includes(q)) : kinds;
    },
  };
}
