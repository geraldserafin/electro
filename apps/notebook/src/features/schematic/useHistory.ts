// Undo / redo for the drawing: each change the user makes is one step (a drag is one, however long).
import { useRef } from "react";
import type { SchematicData } from "@/shared/model/types";

const HISTORY = 100;

export function useHistory(value: SchematicData, onChange: (value: SchematicData) => void) {
  const history = useRef<{ past: SchematicData[]; future: SchematicData[] }>({ past: [], future: [] });
  /** ``next`` as one step; ``before``: what it was (for a drag: when it started). */
  const commit = (next: SchematicData, before: SchematicData = value) => {
    history.current.past = [...history.current.past.slice(-HISTORY + 1), before];
    history.current.future = [];
    onChange(next);
  };
  const undo = () => {
    const previous = history.current.past.pop();
    if (!previous) return false;
    history.current.future.push(value);
    onChange(previous);
    return true;
  };
  const redo = () => {
    const next = history.current.future.pop();
    if (!next) return;
    history.current.past.push(value);
    onChange(next);
  };
  return { commit, undo, redo };
}
