import type { CSSProperties } from "react";
import { Bone } from "@/shared/ui/Skeleton";

/** Cards of the notes list, while it loads. */
export function CardSkeletons({ count = 3 }: { count?: number }) {
  return (
    <>
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className="card card-skeleton" aria-hidden style={{ "--i": i } as CSSProperties}>
          <span className="thumb skeleton" />
          <Bone w="70%" h={14} />
          <Bone w="40%" h={11} style={{ marginTop: 6 }} />
        </div>
      ))}
    </>
  );
}
