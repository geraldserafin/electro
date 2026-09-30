// / — the user's library: their own folders and notes; a new note or folder; a note from a file (at
// the top). Under it, the courses and examples (features/examples).
import { Result, useAtomRefresh, useAtomValue } from "@effect-atom/atom-react";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { COURSES, CourseCard } from "@/features/examples";
import { LibraryGrid } from "@/features/library";
import { CardSkeletons, homeAtom, useCreateNote } from "@/features/notes";
import { SettingsMenu } from "@/features/settings";
import { useTitle } from "@/shared/hooks/useTitle";
import { cn } from "@/shared/lib/cn";
import { copyOf, FormatError, upload } from "@/shared/model/format";
import { Credits, Islands } from "@/shared/ui/Island";
import { Upload } from "@/shared/ui/icons";
import { MenuItem } from "@/shared/ui/Menu";

const grid =
  "grid grid-cols-[repeat(auto-fill,212px)] gap-x-6 gap-y-7 max-sm:grid-cols-[repeat(2,212px)] max-sm:justify-between max-sm:gap-x-4 max-sm:[zoom:0.74]";
const note = "mt-6 mb-3.5 text-[14px] text-muted";

export function Home() {
  const { t } = useTranslation("pages", { keyPrefix: "home" });
  const { t: tLibrary } = useTranslation("library");
  const { t: tFile } = useTranslation("pages", { keyPrefix: "file" });
  useTitle(null);
  const items = useAtomValue(homeAtom);
  const refresh = useAtomRefresh(homeAtom);
  useEffect(refresh, [refresh]); // things change on their own pages: read the home screen afresh on coming back
  const create = useCreateNote();
  const fileInput = useRef<HTMLInputElement>(null);
  const [problem, setProblem] = useState<string | null>(null);

  const start = async (make: () => Promise<Parameters<typeof create>[0]>) => {
    try {
      setProblem(null);
      if (!(await create(await make()))) setProblem(t("createFailed"));
    } catch (error) {
      setProblem(
        error instanceof FormatError ? tFile(error.issue.type, error.issue) : String((error as Error).message ?? error),
      );
    }
  };

  return (
    <div>
      <Islands side="left">{null /* nothing on the left: its half of the band on a phone */}</Islands>
      <Islands side="right">
        <input
          ref={fileInput}
          type="file"
          accept=".json"
          hidden
          onChange={(e) => {
            const file = e.target.files?.[0];
            e.target.value = "";
            if (file) void start(async () => copyOf(await upload(file)));
          }}
        />
        <SettingsMenu
          actions={
            <MenuItem icon={<Upload />} onSelect={() => fileInput.current?.click()}>
              {t("openFile")}…
            </MenuItem>
          }
        />
      </Islands>

      <div className="mx-auto max-w-310 px-8 max-sm:px-4 pt-21 pb-24">
        <h1 className="mt-0 mb-5 text-[22px] font-medium">{tLibrary("home")}</h1>
        {problem && <p className={cn(note, "text-danger")}>{problem}</p>}
        {Result.isSuccess(items) ? (
          <LibraryGrid
            items={items.value}
            parentId={null}
            container={null}
            label={tLibrary("home")}
            onProblem={setProblem}
          />
        ) : (
          <ul className={grid}>{Result.isFailure(items) ? null : <CardSkeletons />}</ul>
        )}
        {Result.isFailure(items) && <p className={note}>{t("listUnavailable")}</p>}

        <h2 className="mt-12 mb-4 text-[16px] font-medium text-muted">{t("courses")}</h2>
        <ul className={grid} aria-label={t("courses")}>
          {COURSES.map((course, i) => (
            <CourseCard key={course.slug} course={course} index={i} />
          ))}
        </ul>
        <Credits madeBy={t("madeBy")} />
      </div>
    </div>
  );
}
