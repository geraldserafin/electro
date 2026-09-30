// /examples/:course/:name — a lesson, to read, change and run; nothing of it is saved until the user
// adds it to their notes (a copy of their own, under its title). The way back: its course.
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router";
import { course as findCourse, lesson } from "@/features/examples";
import { Notebook } from "@/features/notebook";
import type { Notebook as NotebookData } from "@/shared/model/types";
import { PageMessage } from "@/shared/ui/PageMessage";

export function ExamplePage() {
  const { t } = useTranslation("pages", { keyPrefix: "example" });
  const { t: tNote } = useTranslation("notebook");
  const { course: slug = "", name = "" } = useParams();
  const course = findCourse(slug);
  const [notebook, setNotebook] = useState<NotebookData | "missing" | null>(null);

  useEffect(() => {
    let alive = true;
    setNotebook(null);
    const found = lesson(slug, name);
    if (!found) setNotebook("missing");
    else
      void found.then(
        (nb) => alive && setNotebook(nb),
        () => alive && setNotebook("missing"),
      );
    return () => {
      alive = false;
    };
  }, [slug, name]);

  if (notebook === "missing")
    return (
      <PageMessage title={t("missing", { name })}>
        <p>
          <Link to="/">{tNote("allNotes")}</Link>
        </p>
      </PageMessage>
    );
  if (!notebook) return null; // (in the bundle: a moment)
  return (
    <Notebook
      key={`${slug}/${name}`}
      initial={notebook}
      revision={null}
      reload={() => {}}
      readOnly
      example
      back={course ? { to: `/examples/${course.slug}`, label: course.title } : { to: "/", label: tNote("allNotes") }}
    />
  );
}
