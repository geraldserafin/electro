// A text cell: the rendered text, or — while editing — its plain Markdown. Clicking the text (or
// the pencil on the side) edits it; leaving the field (or the eye, Esc, Shift+Enter) shows it.
import { useLayoutEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import type { Cell } from "@/shared/model/types";
import { Eye, Pencil } from "@/shared/ui/icons";
import { Markdown } from "@/shared/ui/Markdown";
import { gutter } from "./RunButton";

export function MarkdownCell({ cell, update }: { cell: Extract<Cell, { type: "markdown" }>; update: (patch: Partial<Cell>) => void }) {
  const { t } = useTranslation("notebook");
  const [editing, setEditing] = useState(cell.source === "");
  const field = useRef<HTMLTextAreaElement>(null);
  // the field grows with the text, so the page scrolls, not the field
  useLayoutEffect(() => {
    const el = field.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight + 2}px`;
  }, [editing, cell.source]);
  const toggle = editing ? t("markdown.show") : t("markdown.edit");
  return (
    <div className="flex gap-2 items-start">
      <div className={gutter}>
        {/* mouse down would take the focus from the field (and show the text) before the click */}
        <button onMouseDown={(e) => e.preventDefault()} onClick={() => setEditing(!editing)}
                title={toggle} aria-label={toggle} aria-pressed={editing}
                className="size-7.5 p-0 justify-center rounded-lg text-faint opacity-0 transition-opacity duration-150
                           group-hover/cell:opacity-100 group-data-focused/cell:opacity-100 hover:text-fg hover:bg-hover
                           aria-pressed:opacity-100 aria-pressed:text-fg aria-pressed:bg-selected">
          {editing ? <Eye /> : <Pencil />}
        </button>
      </div>
      <div className="flex-1 min-w-0">
        {editing ? (
          <textarea
            ref={field}
            className="block w-full resize-none overflow-hidden px-3 py-2.5 rounded-lg border-none bg-code-bg font-mono text-[16px] leading-[1.6]
                       focus:outline-1 focus:outline-line"
            autoFocus
            value={cell.source}
            spellCheck={false}
            placeholder={t("markdown.placeholder")}
            onChange={(e) => update({ source: e.target.value })}
            onBlur={() => setEditing(false)}
            onKeyDown={(e) => {
              if (e.key === "Escape" || (e.key === "Enter" && e.shiftKey)) {
                e.preventDefault();
                setEditing(false);
              }
            }}
          />
        ) : (
          <div className="px-2 py-1 max-[760px]:pl-0 min-h-[1.6em] rounded-lg cursor-text [&_:is(h1,h2,h3)]:scroll-mt-18"
               onClick={(e) => (e.target as HTMLElement).closest("a") || setEditing(true)} title={t("markdown.clickToEdit")}>
            <Markdown source={cell.source || t("markdown.empty")} />
          </div>
        )}
      </div>
    </div>
  );
}
