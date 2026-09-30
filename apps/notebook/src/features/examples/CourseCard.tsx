// A course on the home screen: a folder's card, with the first pages of its first lessons.
import { previewOf } from "@electro/notes-api";
import { useTranslation } from "react-i18next";
import { FolderThumb } from "@/features/library";
import { Card, toDocument } from "@/features/notes";
import { library } from "@/features/schematic";
import { type Course, useLessons } from "./examples";

export function CourseCard({ course, index }: { course: Course; index: number }) {
  const { t } = useTranslation("pages", { keyPrefix: "course" });
  const first = useLessons(course, 4);
  const previews = (first ?? []).map(({ notebook }) => previewOf(toDocument(notebook)));
  return (
    <Card
      index={index}
      to={`/examples/${course.slug}`}
      title={course.title}
      meta={t("lessons", { count: course.lessons.length })}
      thumb={<FolderThumb previews={previews} library={library} />}
      library={library}
    />
  );
}
