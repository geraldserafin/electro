// Someone's picture (from the provider they signed in with), or the first letter of their name.
import { cn } from "@/shared/lib/cn";

export function Avatar({ name, url, className }: { name: string; url: string | null; className?: string }) {
  const size = cn("size-7 flex-none rounded-full", className);
  return url ? (
    <img src={url} alt="" referrerPolicy="no-referrer" className={size} />
  ) : (
    <span className={cn(size, "grid place-items-center bg-selected text-[13px] font-medium")}>
      {name.slice(0, 1).toUpperCase()}
    </span>
  );
}
