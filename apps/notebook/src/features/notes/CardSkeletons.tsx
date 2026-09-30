import { Bone } from "@/shared/ui/Skeleton";

/** Cards of the notes list, while it loads. */
export function CardSkeletons({ count = 3 }: { count?: number }) {
  return (
    <>
      {Array.from({ length: count }, (_, i) => (
        <li key={i} className="grid gap-1" aria-hidden>
          <span className="skeleton w-full aspect-[794/1123] mb-2" />
          <Bone w="70%" h={14} />
          <Bone w="40%" h={11} style={{ marginTop: 6 }} />
        </li>
      ))}
    </>
  );
}
