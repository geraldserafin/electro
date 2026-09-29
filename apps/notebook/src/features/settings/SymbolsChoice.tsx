// The symbols' standard of the note open: IEC 60617 (a resistor is a box) or IEEE 315 (a zigzag).
// A row of the ⋯ menu's preferences; it goes with the note.
import { useTranslation } from "react-i18next";
import type { SymbolStandard } from "@/shared/model/types";
import { MenuRow, MenuSelect } from "@/shared/ui/Menu";

export function SymbolsChoice({ value, onChange }: { value: SymbolStandard; onChange: (standard: SymbolStandard) => void }) {
  const { t } = useTranslation("settings");
  return (
    <MenuRow label={t("symbols.label")}>
      <MenuSelect label={t("symbols.label")} value={value} onChange={onChange}
                  options={[{ value: "iec", label: "IEC 60617" }, { value: "ieee", label: "IEEE 315" }]} />
    </MenuRow>
  );
}
