// A note's title in the sidebar: a plain box; a click edits it (like a schematic's name).
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { cn } from "@/shared/lib/cn";

const box = "h-9 max-w-105 rounded-lg text-[16px] font-medium";

export function TitleBox({ title, onChange }: { title: string; onChange: (title: string) => void }) {
  const { t } = useTranslation("notebook");
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(title);
  const commit = () => {
    setEditing(false);
    if (draft !== title) onChange(draft.trim());
  };
  if (!editing)
    return (
      <button className={cn(box, "block flex-1 min-w-0 px-2.5 py-1.5 leading-6 text-left truncate", !title && "text-muted font-normal")}
              onClick={() => { setDraft(title); setEditing(true); }} title={t("editTitle")}>
        {title || t("untitled")}
      </button>
    );
  return (
    <input className={cn(box, "px-2.25 py-1.25")} autoFocus value={draft} placeholder={t("untitled")} aria-label={t("noteTitle")}
           spellCheck={false} size={Math.max(12, draft.length + 1)}
           onChange={(e) => setDraft(e.target.value)} onBlur={commit}
           onKeyDown={(e) => {
             if (e.key === "Enter") commit();
             if (e.key === "Escape") { setDraft(title); setEditing(false); }
           }} />
  );
}
