// A dialog over the page, dimmed behind it: a click beside it or Esc closes it.
import { type ReactNode, useEffect } from "react";
import { cn } from "@/shared/lib/cn";

export function Dialog({
  label,
  onClose,
  className,
  children,
}: {
  label: string;
  onClose: () => void;
  className?: string;
  children: ReactNode;
}) {
  useEffect(() => {
    const esc = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [onClose]);
  return (
    <div className="fixed inset-0 z-100 grid place-items-center bg-black/25 p-4" onClick={onClose} data-keep-focus>
      <div
        role="dialog"
        aria-modal
        aria-label={label}
        className={cn(
          "grid gap-2 w-full max-w-110 max-h-[80vh] p-4 rounded-xl border border-line bg-paper shadow-menu",
          className,
        )}
        onClick={(e) => e.stopPropagation()}
      >
        {children}
      </div>
    </div>
  );
}
