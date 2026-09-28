import { useTranslation } from "react-i18next";

/** When a note was changed, for its card: "today, 14:05", or the date. */
export function useWhen() {
  const { t, i18n } = useTranslation("notes");
  return (iso: string) => {
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return "";
    if (new Date().toDateString() !== date.toDateString())
      return date.toLocaleDateString(i18n.language, { day: "numeric", month: "long", year: "numeric" });
    return t("today", { time: date.toLocaleTimeString(i18n.language, { hour: "2-digit", minute: "2-digit" }) });
  };
}
