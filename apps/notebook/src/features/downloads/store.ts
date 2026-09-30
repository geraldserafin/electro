// What the workers are downloading (shared/lib/trackDownloads.ts), gathered on the page: each file,
// by its group — Python, the compiler, a board's libraries.
import { useSyncExternalStore } from "react";
import type { Progress } from "@/shared/lib/trackDownloads";

export type { Progress };

let files: Record<string, Progress> = {};
const listeners = new Set<() => void>();

/** A worker's message about a file. */
export function report(p: Progress) {
  files = { ...files, [p.key]: p };
  for (const l of listeners) l();
}

export const useDownloads = () =>
  useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    () => files,
  );

export interface Group {
  group: string;
  loaded: number;
  total: number; // the files' sizes as far as they are known
  known: boolean; // every file said its size, honestly: "of how much" can be told
  fraction: number; // 0–1
  files: number;
  done: boolean;
  error: string | null;
}

/** A file's share done: by its bytes, when its size is known and honest (compressed on the way, the
 *  size said is the smaller one), else half until it is done. */
const fractionOf = (p: Progress) =>
  p.done ? 1 : p.total && p.loaded <= p.total ? Math.min(0.99, p.loaded / p.total) : 0.5;

export function groups(all: Record<string, Progress>): Group[] {
  const by = new Map<string, Progress[]>();
  for (const p of Object.values(all)) by.set(p.group, [...(by.get(p.group) ?? []), p]);
  return [...by.entries()].map(([group, ps]) => {
    // weighed by size, where known (a big file counts for more than a small one)
    const weight = (p: Progress) => Math.max(p.total, p.loaded, 1);
    const sum = ps.reduce((s, p) => s + weight(p), 0);
    return {
      group,
      loaded: ps.reduce((s, p) => s + p.loaded, 0),
      total: ps.reduce((s, p) => s + Math.max(p.total, p.loaded), 0),
      known: ps.every((p) => p.total > 0 && p.loaded <= p.total),
      fraction: ps.reduce((s, p) => s + fractionOf(p) * weight(p), 0) / sum,
      files: ps.length,
      done: ps.every((p) => p.done),
      error: ps.find((p) => p.error)?.error ?? null,
    };
  });
}
