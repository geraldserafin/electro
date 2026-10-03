// A dialog over the page, the page dimmed and blurred behind it: it comes forward, and goes back
// (a click beside it, Esc, or useDialogClose: closed once it has gone).
import { createContext, type ReactNode, useCallback, useContext, useEffect, useState } from "react";
import { cn } from "@/shared/lib/cn";

const Closing = createContext<() => void>(() => {});
/** Closing the dialog this is in, as a click beside it does: after it has gone back. */
export const useDialogClose = () => useContext(Closing);

const still = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

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
  const [leaving, setLeaving] = useState(false);
  const close = useCallback(() => (still() ? onClose() : setLeaving(true)), [onClose]);
  useEffect(() => {
    const esc = (e: KeyboardEvent) => e.key === "Escape" && close();
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [close]);
  return (
    <Closing.Provider value={close}>
      <div
        className={cn(
          "fixed inset-0 z-100 grid place-items-center bg-scrim backdrop-blur-[3px] p-4",
          leaving ? "animate-fade-out" : "animate-fade-in",
        )}
        onClick={close}
        data-keep-focus
      >
        <div
          role="dialog"
          aria-modal
          aria-label={label}
          className={cn(
            "grid gap-2 w-full max-w-110 max-h-[80vh] p-4 rounded-xl border border-line bg-paper shadow-menu",
            leaving ? "animate-dialog-out" : "animate-dialog-in",
            className,
          )}
          onClick={(e) => e.stopPropagation()}
          onAnimationEnd={(e) => leaving && e.target === e.currentTarget && onClose()}
        >
          {children}
        </div>
      </div>
    </Closing.Provider>
  );
}
