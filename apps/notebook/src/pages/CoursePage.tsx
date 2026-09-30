// /examples/:course — a course: what it teaches, its lessons (each opens to read and try, saved
// nowhere: ExamplePage), and the whole of it added to the notes at once, as a folder.
import { useAtomSet } from "@effect-atom/atom-react";
import { previewOf } from "@electro/notes-api";
import { Exit } from "effect";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams } from "react-router";
import { course as findCourse, fromExample, useLessons } from "@/features/examples";
import { Card, CardSkeletons, createFolder, folderUrl, LIBRARY, saveNote, toDocument } from "@/features/notes";
import { library } from "@/features/schematic";
import { SettingsMenu } from "@/features/settings";
import { useTitle } from "@/shared/hooks/useTitle";
import { IslandLink, Islands } from "@/shared/ui/Island";
import { Back } from "@/shared/ui/icons";
import { PageMessage } from "@/shared/ui/PageMessage";

const grid =
  "grid w-full grid-cols-[repeat(auto-fill,minmax(180px,1fr))] gap-x-6 gap-y-7 max-sm:grid-cols-2 max-sm:gap-x-4 max-sm:gap-y-5";

export function CoursePage() {
  const { t } = useTranslation("pages", { keyPrefix: "course" });
  const { t: tLibrary } = useTranslation("library");
  const { course: slug = "" } = useParams();
  const course = findCourse(slug);
  useTitle(course?.title ?? t("missing"));
  const lessons = useLessons(course);
  const folder = useAtomSet(createFolder, { mode: "promiseExit" });
  const save = useAtomSet(saveNote, { mode: "promiseExit" });
  const navigate = useNavigate();
  const [problem, setProblem] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);

  const back = (
    <Islands side="left">
      <IslandLink to="/" title={tLibrary("home")} aria-label={tLibrary("home")}>
        <Back />
      </IslandLink>
    </Islands>
  );
  if (!course)
    return (
      <>
        {back}
        <PageMessage title={t("missing")}>
          <p>
            <Link to="/">{tLibrary("home")}</Link>
          </p>
        </PageMessage>
      </>
    );

  const addAll = async () => {
    setProblem(null);
    setAdding(true);
    try {
      const made = await folder({ payload: { name: course.title, parentId: null }, reactivityKeys: LIBRARY });
      if (Exit.isFailure(made)) throw new Error("folder");
      for (const name of course.lessons) {
        const notebook = (await fromExample(course.slug, name))!;
        const saved = await save({
          path: { id: notebook.id },
          payload: { document: toDocument(notebook), baseRevision: null, parentId: made.value.id },
          reactivityKeys: LIBRARY,
        });
        if (Exit.isFailure(saved)) throw new Error("note");
      }
      navigate(folderUrl(made.value.id, course.title));
    } catch {
      setProblem(t("addFailed"));
    } finally {
      setAdding(false);
    }
  };

  return (
    <div>
      {back}
      <Islands side="right">
        <SettingsMenu />
      </Islands>
      <div className="mx-auto max-w-310 px-8 max-sm:px-4 pt-21 pb-24">
        <h1 className="mt-0 mb-2 text-[22px] font-medium">{course.title}</h1>
        <p className="mt-0 mb-2 max-w-170 text-[15px] leading-relaxed">{course.description}</p>
        <p className="mt-0 mb-5 max-w-170 text-[14px] text-muted">{t("hint")}</p>
        <button
          className="mb-8 rounded-lg border border-line px-3.5 py-1.5 text-[14px] hover:border-fg disabled:opacity-60"
          onClick={() => void addAll()}
          disabled={adding}
        >
          {adding ? t("adding") : t("addAll")}
        </button>
        {problem && <p className="mt-0 mb-4 text-[14px] text-danger">{problem}</p>}
        <ul className={grid} aria-label={course.title}>
          {lessons ? (
            lessons.map(({ name, notebook }, i) => (
              <Card
                key={name}
                index={i}
                title={notebook.title}
                meta={t("lesson", { n: i + 1 })}
                library={library}
                preview={previewOf(toDocument(notebook))}
                to={`/examples/${course.slug}/${name}`}
              />
            ))
          ) : (
            <CardSkeletons />
          )}
        </ul>
      </div>
    </div>
  );
}
