// The components the user made (a drawing, its ports the pins of a box: PartDef), kept in the vault
// (components/<id>.json: with the notes, on GitHub too) and offered in every board's element
// library. Placed on a drawing, a component's definition is copied into it (SchematicData.parts):
// the note stays whole on its own.
import { useEffect, useSyncExternalStore } from "react";
import { vault } from "@/features/vault";
import type { PartDef } from "@/shared/model/types";

export interface Component {
  id: string;
  def: PartDef;
}

let current: Component[] = [];
let loaded: Promise<void> | null = null;
const listeners = new Set<() => void>();
const tell = () => {
  for (const l of listeners) l();
};

const isDef = (d: unknown): d is PartDef => {
  const o = d as PartDef | null;
  return (
    !!o &&
    typeof o.name === "string" &&
    Array.isArray(o.size) &&
    o.size.length === 2 &&
    Array.isArray(o.pins) &&
    o.pins.every((p) => typeof p?.name === "string" && ["left", "right", "top", "bottom"].includes(p.side)) &&
    !!o.schematic &&
    Array.isArray(o.schematic.elements) &&
    Array.isArray(o.schematic.wires)
  );
};

/** Read them afresh from the vault (after a save brought GitHub's, or another tab changed them). */
export function reload(): Promise<void> {
  loaded = vault()
    .components()
    .then((found) => {
      current = found
        .flatMap(({ id, data }) => (isDef(data) ? [{ id, def: data }] : []))
        .sort((a, b) => a.def.name.localeCompare(b.def.name));
      tell();
    })
    .catch((e) => console.warn("The components could not be read", e));
  return loaded;
}

/** The user's components, by name; the list follows every change. */
export function useComponents(): Component[] {
  useEffect(() => {
    if (!loaded) void reload();
    const pulled = () => void reload();
    window.addEventListener("electro:pulled", pulled);
    return () => window.removeEventListener("electro:pulled", pulled);
  }, []);
  return useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    () => current,
  );
}

/** Stored (under ``id``: it replaces that one); its id. */
export async function saveComponent(def: PartDef, id: string = crypto.randomUUID().replaceAll("-", "").slice(0, 12)) {
  await vault().putComponent(id, def);
  await reload();
  return id;
}

export async function removeComponent(id: string) {
  await vault().removeComponent(id);
  await reload();
}
