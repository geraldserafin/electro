// A text cell. Read, it is the page itself — the rendered text, no frame (a note reads like a
// document). Clicked, it becomes a block like the code's: a bar with two tabs, its Markdown and the
// preview, and the one chosen under it. Leaving the cell (a click elsewhere, Esc, Shift+Enter)
// shows the text again.
import { type ReactNode, useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useClickOutside } from "@/shared/hooks/useClickOutside";
import type { Cell } from "@/shared/model/types";
import { Eye, Pencil } from "@/shared/ui/icons";
import { Markdown } from "@/shared/ui/Markdown";
import { block, CellBar, tabLook, useCellFocused } from "./CellBar";

type Mode = "edit" | "preview";

export function MarkdownCell({
  cell,
  update,
}: {
  cell: Extract<Cell, { type: "markdown" }>;
  update: (patch: Partial<Cell>) => void;
}) {
  const { t } = useTranslation("notebook");
  const focused = useCellFocused();
  const [open, setOpen] = useState<Mode | null>(cell.source === "" ? "edit" : null);
  const ref = useRef<HTMLDivElement>(null);
  const field = useRef<HTMLTextAreaElement>(null);
  const close = useCallback(() => setOpen(null), []);
  // a finger: the first tap takes the cell up, the second opens it (a tap meant for something else does not).
  // The tap that takes it up has it taken up by the time it reaches the text (the frame's, on the way
  // down, drawn at once): when it was taken up tells
  const takenAt = useRef(0);
  const wasFocused = useRef(focused);
  if (focused !== wasFocused.current) {
    wasFocused.current = focused;
    if (focused) takenAt.current = performance.now();
  }
  const firstTap = useRef(false);
  useClickOutside(ref, open !== null, close);
  useEffect(() => {
    if (!focused) close();
  }, [focused, close]); // another cell taken up
  // the field grows with the text, so the page scrolls, not the field
  useLayoutEffect(() => {
    const el = field.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight + 2}px`;
  }, [open, cell.source]);

  const text = (
    <div
      className="px-3 py-1 min-h-[1.6em] cursor-text [&_:is(h1,h2,h3)]:scroll-mt-18"
      onPointerDown={(e) => {
        firstTap.current = e.pointerType === "touch" && (!focused || performance.now() - takenAt.current < 100);
      }}
      onClick={(e) => {
        if ((e.target as HTMLElement).closest("a")) return;
        if (firstTap.current) return;
        setOpen("edit");
      }}
      title={t("markdown.clickToEdit")}
    >
      <Markdown source={cell.source || t("markdown.empty")} />
    </div>
  );
  if (!open) return <div ref={ref}>{text}</div>;

  const tab = (mode: Mode, label: string, name: string, icon: ReactNode) => (
    // mouse down would take the focus from the field before the click
    <button
      role="tab"
      aria-selected={open === mode}
      aria-label={name}
      title={name}
      className={tabLook(open === mode)}
      onMouseDown={(e) => e.preventDefault()}
      onClick={() => setOpen(mode)}
    >
      {icon} {label}
    </button>
  );
  return (
    <div
      ref={ref}
      className={block}
      onKeyDown={(e) => {
        if (e.key === "Escape" || (e.key === "Enter" && e.shiftKey)) {
          e.preventDefault();
          close();
        }
      }}
    >
      <CellBar
        label={t("cell.tabs")}
        tabs={
          <>
            {tab("edit", "Markdown", t("markdown.edit"), <Pencil />)}
            {tab("preview", t("markdown.preview"), t("markdown.show"), <Eye />)}
          </>
        }
      />
      {open === "edit" ? (
        <textarea
          ref={field}
          className="block w-full resize-none overflow-hidden px-3 py-2.5 border-none bg-code-bg font-mono text-[16px] leading-[1.6] outline-none"
          autoFocus
          value={cell.source}
          spellCheck={false}
          placeholder={t("markdown.placeholder")}
          onChange={(e) => update({ source: e.target.value })}
        />
      ) : (
        <div className="bg-bg py-1.5">{text}</div>
      )}
    </div>
  );
}
