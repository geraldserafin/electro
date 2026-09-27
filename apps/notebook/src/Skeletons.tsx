// Placeholders in the shape of what is coming, shimmering while it loads.
import type { CSSProperties } from "react";

const Bone = ({ w, h = 14, style }: { w: string | number; h?: number; style?: CSSProperties }) => (
  <span className="skeleton" style={{ width: w, height: h, ...style }} />
);

/** Cards of the notes list. */
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

/** A note on its way: the sidebar, the title, a few paragraphs and a block. */
export function NoteSkeleton() {
  return (
    <div className="note-skeleton" aria-busy aria-label="Wczytuję notatkę">
      <aside className="note-nav open">
        <Bone w="75%" h={16} style={{ margin: "10px 10px 18px" }} />
        {[62, 80, 54, 70, 45].map((w, i) => <Bone key={i} w={`${w}%`} h={12} style={{ margin: "9px 12px" }} />)}
      </aside>
      <main className="with-nav">
        <Bone w="55%" h={34} style={{ marginLeft: 65, marginBottom: 32 }} />
        {[96, 88, 72].map((w, i) => <Bone key={i} w={`calc(${w}% - 65px)`} style={{ marginLeft: 65, marginBottom: 12 }} />)}
        <Bone w="calc(100% - 56px)" h={140} style={{ marginLeft: 56, margin: "28px 0 28px 56px", borderRadius: 10 }} />
        {[92, 60].map((w, i) => <Bone key={i} w={`calc(${w}% - 65px)`} style={{ marginLeft: 65, marginBottom: 12 }} />)}
      </main>
    </div>
  );
}
