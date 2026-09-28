// "Układ 1" in the board's corner; a click edits it. In code the schematic is the variable układ1.
import { useState } from "react";
import { useTranslation } from "react-i18next";

export function NameBox({ name, onRename }: { name: string; onRename: (name: string) => void }) {
  const { t } = useTranslation("notebook");
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(name);
  const commit = () => {
    setEditing(false);
    if (draft.trim()) onRename(draft.trim());
    else setDraft(name);
  };
  if (!editing)
    return (
      <button className="px-2.5 py-1 rounded-lg text-[15px] font-medium" onClick={() => { setDraft(name); setEditing(true); }}
              title={t("schematic.nameTitle", { variable: variableName(name) })}>
        {name}
      </button>
    );
  return (
    <span className="flex flex-col gap-0.5 p-0.5">
      <input className="w-45 px-2 py-1 text-[15px]" autoFocus value={draft} spellCheck={false} aria-label={t("schematic.name")}
             onChange={(e) => setDraft(e.target.value)} onBlur={commit}
             onKeyDown={(e) => {
               if (e.key === "Enter") commit();
               if (e.key === "Escape") { setDraft(name); setEditing(false); }
             }} />
      <small className="px-1 pb-0.5 text-[12px] text-muted">{t("schematic.inCode")} <code className="font-mono text-fg">{variableName(draft)}</code></small>
    </span>
  );
}

/** Mirrors kernel.variable(): "Układ 1" → układ1. */
export function variableName(name: string): string {
  const v = name.toLowerCase().replace(/[^\p{L}\p{N}_]/gu, "");
  if (!v) return "uklad";
  return /^\p{N}/u.test(v) ? `_${v}` : v;
}
