import { Bone } from "@/shared/ui/Skeleton";

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
