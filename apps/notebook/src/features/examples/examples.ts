// The example notebooks, in courses: examples/<course>/course.json (its title, what it teaches, its
// place) and its lessons, examples/<course>/NN-name.electro.json, in the order of their names. A
// lesson is started as a new note (/examples/:course/:lesson); a whole course, as a folder of them.
// The lessons are read only when a course is looked at (they are big: sketches, outputs).
import { useEffect, useState } from "react";
import { copyOf } from "@/shared/model/format";
import type { Notebook } from "@/shared/model/types";

export interface Course {
  slug: string; // its directory: "1-elektronika"
  title: string;
  description: string;
  lessons: string[]; // their names: "01-prad"
}

const infos = import.meta.glob<{ title: string; description: string }>("../../../examples/*/course.json", {
  eager: true,
  import: "default",
});
const files = import.meta.glob<Notebook>("../../../examples/*/*.electro.json", { import: "default" });

const parts = (path: string) => {
  const [course, file] = path.split("/").slice(-2);
  return { course, lesson: file.replace(".electro.json", "") };
};

export const COURSES: Course[] = Object.entries(infos)
  .map(([path, info]) => {
    const { course } = parts(path);
    const lessons = Object.keys(files)
      .map(parts)
      .filter((p) => p.course === course)
      .map((p) => p.lesson)
      .sort();
    return { slug: course, ...info, lessons };
  })
  .sort((a, b) => a.slug.localeCompare(b.slug, undefined, { numeric: true }));

export const course = (slug: string) => COURSES.find((c) => c.slug === slug) ?? null;

const cache = new Map<string, Promise<Notebook>>();
/** A lesson as it is (not a copy: see fromExample); null when there is none. */
export function lesson(courseSlug: string, name: string): Promise<Notebook> | null {
  const key = `../../../examples/${courseSlug}/${name}.electro.json`;
  const load = files[key];
  if (!load) return null;
  if (!cache.has(key)) cache.set(key, load());
  return cache.get(key)!;
}

/** A new note from a lesson: the same content, its own identity (null: no such lesson). */
export const fromExample = async (courseSlug: string, name: string): Promise<Notebook | null> => {
  const found = lesson(courseSlug, name);
  return found ? copyOf(await found) : null;
};

/** The first ``count`` lessons of a course (all: without it), once they are read. */
export function useLessons(c: Course | null, count?: number): { name: string; notebook: Notebook }[] | null {
  const [loaded, setLoaded] = useState<{ name: string; notebook: Notebook }[] | null>(null);
  useEffect(() => {
    if (!c) return;
    let live = true;
    const names = c.lessons.slice(0, count);
    void Promise.all(names.map((name) => lesson(c.slug, name)!)).then(
      (notebooks) => live && setLoaded(notebooks.map((notebook, i) => ({ name: names[i], notebook }))),
    );
    return () => {
      live = false;
    };
  }, [c, count]);
  return loaded;
}
