import type { ReactNode } from "react";

/** A page that has nothing else to show: loading, missing, the server down. */
export function PageMessage({ title, children }: { title?: ReactNode; children?: ReactNode }) {
  return (
    <div className="mx-auto my-24 max-w-140 px-6 text-center [&_p]:my-4.5 [&_a]:text-accent [&_a]:underline">
      {title && <h1 className="mb-2 text-[22px] font-medium">{title}</h1>}
      {children}
    </div>
  );
}
