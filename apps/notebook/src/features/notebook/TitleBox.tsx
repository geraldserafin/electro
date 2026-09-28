// A note's title in the top-left island: a plain box; a click edits it (like a schematic's name).
import { useState } from "react";

export function TitleBox({ title, onChange }: { title: string; onChange: (title: string) => void }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(title);
  const commit = () => {
    setEditing(false);
    if (draft !== title) onChange(draft.trim());
  };
  if (!editing)
    return (
      <button className={`title-box ${title ? "" : "untitled"}`} onClick={() => { setDraft(title); setEditing(true); }}
              title="Kliknij, żeby zmienić tytuł">
        {title || "Bez tytułu"}
      </button>
    );
  return (
    <input className="title-edit" autoFocus value={draft} placeholder="Bez tytułu" aria-label="Tytuł notatki"
           spellCheck={false} size={Math.max(12, draft.length + 1)}
           onChange={(e) => setDraft(e.target.value)} onBlur={commit}
           onKeyDown={(e) => {
             if (e.key === "Enter") commit();
             if (e.key === "Escape") { setDraft(title); setEditing(false); }
           }} />
  );
}
