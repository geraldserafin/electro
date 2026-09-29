import { useTranslation } from "react-i18next";
import { Bone } from "@/shared/ui/Skeleton";
import { column, sidebar } from "./layout";
import { cn } from "@/shared/lib/cn";

/** A note on its way: the sidebar, the title, a few paragraphs and a block. */
export function NoteSkeleton() {
  const { t } = useTranslation("notebook");
  return (
    <div aria-busy aria-label={t("loading")}>
      <aside className={cn(sidebar(true), "max-[900px]:hidden")}>
        <Bone w="75%" h={16} style={{ margin: "10px 10px 18px" }} />
        {[62, 80, 54, 70, 45].map((w, i) => <Bone key={i} w={`${w}%`} h={12} style={{ margin: "9px 12px" }} />)}
      </aside>
      <main className={cn(column(true), "pt-22")}>
        <Bone w="55%" h={34} style={{ marginLeft: 12, marginBottom: 32 }} />
        {[96, 88, 72].map((w, i) => <Bone key={i} w={`calc(${w}% - 12px)`} style={{ marginLeft: 12, marginBottom: 12 }} />)}
        <Bone w="100%" h={140} style={{ margin: "28px 0", borderRadius: 12 }} />
        {[92, 60].map((w, i) => <Bone key={i} w={`calc(${w}% - 12px)`} style={{ marginLeft: 12, marginBottom: 12 }} />)}
      </main>
    </div>
  );
}
