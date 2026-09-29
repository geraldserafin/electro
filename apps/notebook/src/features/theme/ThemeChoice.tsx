import { useTranslation } from "react-i18next";
import { Moon, Sun, System } from "@/shared/ui/icons";
import { MenuRow, Segmented } from "@/shared/ui/Menu";
import { useTheme } from "./theme";

/** The theme, a row of the settings menu: light, dark or the system's, as three icons. */
export function ThemeChoice() {
  const { t } = useTranslation("theme");
  const [theme, choose] = useTheme();
  return (
    <MenuRow label={t("label")}>
      <Segmented label={t("label")} value={theme} onChange={choose} options={[
        { value: "light", label: t("light"), icon: <Sun /> },
        { value: "dark", label: t("dark"), icon: <Moon /> },
        { value: "system", label: t("system"), icon: <System /> },
      ]} />
    </MenuRow>
  );
}
