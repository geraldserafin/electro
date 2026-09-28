import { useTranslation } from "react-i18next";
import { BoardIsland } from "./Board";
import type { pl } from "./messages";

const KEYS = ["select", "wire", "library", "numbers", "full", "rotate", "many", "remove", "escape", "undo", "hand", "pan", "wheel", "zoom", "fit"] as const satisfies readonly (keyof typeof pl.help.keys)[];

/** The keyboard shortcuts (and what the mouse does), bottom right. */
export function HelpPanel() {
  const { t } = useTranslation("schematic");
  return (
    <BoardIsland className="bottom-15 right-3 w-75 flex-col items-stretch px-3.5 py-3 text-[13px]">
      <h4 className="mb-1.5 font-bold">{t("help.title")}</h4>
      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.75 m-0">
        {KEYS.map((k) => (
          <div key={k} className="contents">
            <dt className="justify-self-start px-1.25 rounded bg-selected font-mono text-[12px] text-fg">{t(`help.keys.${k}.key`)}</dt>
            <dd className="m-0 text-muted">{t(`help.keys.${k}.what`)}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-2 mb-0 text-[12px] text-muted">{t("help.note")}</p>
    </BoardIsland>
  );
}
