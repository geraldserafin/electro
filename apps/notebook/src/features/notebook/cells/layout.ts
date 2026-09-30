// A schematic cell's editor layout, as an IDE has it: editor groups side by side, each with its
// tabs and the one shown. The files are the drawing ("board"), the circuit's code ("circuit") and
// each Arduino's sketch (its id). Every file always has a tab, in one group: the first group holds
// all those not split off into another; a tab closed there goes back to the first. Two groups at
// most: a left one and a right one. Pure, no React.

export type Side = "left" | "right";
export const MAX = 2; // groups side by side at most
export interface Group {
  tabs: string[];
  active: string;
  size: number;
} // size: its share of the width
export interface Layout {
  groups: Group[];
  focus: number;
} // focus: the group worked in (where files open)

/** Every file open in one group, the drawing (or the code) shown. */
export function initial(files: string[], showCode: boolean): Layout {
  return { groups: [{ tabs: files, active: showCode ? "circuit" : "board", size: 1 }], focus: 0 };
}

/**
 * No empty groups, only files that exist and each of them in a group (the first, when in none),
 * each group showing one of its tabs.
 * The shares of the width add up to the number of groups (a group left alone fills the width: flex
 * gives a share under 1 only that part of the room).
 */
export function clean(layout: Layout, files: string[]): Layout {
  const seen = new Set<string>();
  const groups = layout.groups
    .map((g) => {
      const tabs = g.tabs.filter((f) => files.includes(f) && !seen.has(f) && seen.add(f));
      return { ...g, tabs, active: tabs.includes(g.active) ? g.active : tabs[tabs.length - 1] };
    })
    .filter((g) => g.tabs.length > 0);
  const missing = files.filter((f) => !seen.has(f));
  if (missing.length) {
    if (groups.length) groups[0] = { ...groups[0], tabs: [...groups[0].tabs, ...missing] };
    else groups.push({ tabs: missing, active: missing[0], size: 1 });
  }
  const total = groups.reduce((sum, g) => sum + (g.size > 0 ? g.size : 1), 0);
  return {
    groups: groups.map((g) => ({ ...g, size: ((g.size > 0 ? g.size : 1) / total) * groups.length })),
    focus: Math.min(Math.max(0, layout.focus), groups.length - 1),
  };
}

const where = (layout: Layout, file: string) => layout.groups.findIndex((g) => g.tabs.includes(file));

/** Show ``file``: where it is open already, else as a new tab in the focused group. */
export function open(layout: Layout, file: string, files: string[]): Layout {
  const at = where(layout, file);
  if (at >= 0)
    return clean({ groups: layout.groups.map((g, i) => (i === at ? { ...g, active: file } : g)), focus: at }, files);
  const g = layout.focus;
  return clean(
    { groups: layout.groups.map((x, i) => (i === g ? { ...x, tabs: [...x.tabs, file], active: file } : x)), focus: g },
    files,
  );
}

/** Close ``file``'s tab in a split: it goes back to the first group (the split goes when it was its last). */
export function close(layout: Layout, file: string, files: string[]): Layout {
  return clean(
    {
      ...layout,
      groups: layout.groups.map((g) => {
        const i = g.tabs.indexOf(file);
        if (i < 0) return g;
        const tabs = g.tabs.filter((f) => f !== file);
        return { ...g, tabs, active: g.active === file ? tabs[Math.max(0, i - 1)] : g.active };
      }),
    },
    files,
  );
}

/**
 * ``file`` dragged into group ``to``: its tab there, before the tab now at ``at`` (counted without
 * it; none: at the end) — in its own bar that is putting the tabs in another order.
 */
export function moveTo(layout: Layout, file: string, to: number, files: string[], at?: number): Layout {
  const from = where(layout, file);
  const groups = layout.groups.map((g, i) => {
    const tabs = g.tabs.filter((f) => f !== file);
    if (i === to) {
      const place = Math.max(0, Math.min(at ?? tabs.length, tabs.length));
      return { ...g, tabs: [...tabs.slice(0, place), file, ...tabs.slice(place)], active: file };
    }
    if (i === from) return { ...g, tabs, active: g.active === file ? tabs[tabs.length - 1] : g.active };
    return g;
  });
  return clean({ groups, focus: to }, files);
}

/**
 * ``file`` dragged to the outer edge on ``side``. One group: it splits off to that side. Two: its
 * group goes to that side if the file is alone there (the groups trade places), else the file
 * joins the group on that side.
 */
export function dock(layout: Layout, file: string, side: Side, files: string[]): Layout {
  if (layout.groups.length < 2) return split(layout, file, 0, side, files);
  const from = where(layout, file);
  const target = side === "left" ? 0 : layout.groups.length - 1;
  if (layout.groups[from].tabs.length > 1) return moveTo(layout, file, target, files);
  if (from === target) return layout;
  return clean({ groups: [...layout.groups].reverse(), focus: target }, files);
}

/** ``file`` dragged to one side of group ``to``: a new group there, with it alone (while there are fewer than two). */
export function split(layout: Layout, file: string, to: number, side: Side, files: string[]): Layout {
  if (layout.groups.length >= MAX) return dock(layout, file, side, files);
  const from = where(layout, file);
  if (from === to && layout.groups[from].tabs.length === 1) return layout; // it would split off itself
  const size = layout.groups[to].size / 2;
  const groups: Group[] = [];
  layout.groups.forEach((g, i) => {
    const own = g.tabs.includes(file)
      ? {
          ...g,
          tabs: g.tabs.filter((f) => f !== file),
          active: g.active === file ? g.tabs.filter((f) => f !== file).at(-1)! : g.active,
        }
      : g;
    const fresh: Group = { tabs: [file], active: file, size };
    if (i === to && side === "left") groups.push(fresh);
    groups.push(i === to ? { ...own, size } : own);
    if (i === to && side === "right") groups.push(fresh);
  });
  const kept = groups.filter((g) => g.tabs.length > 0);
  return clean(
    { groups: kept, focus: kept.findIndex((g) => g.tabs.length === 1 && g.tabs[0] === file && g.active === file) },
    files,
  );
}

/**
 * The layout as the notebook shows it (splits are for full screen): one group, every tab in the
 * groups' order, the focused group's file shown. The split is kept for when it is full screen again.
 */
export function flat(layout: Layout): Layout {
  return {
    groups: [{ tabs: layout.groups.flatMap((g) => g.tabs), active: layout.groups[layout.focus].active, size: 1 }],
    focus: 0,
  };
}

/**
 * In the notebook (``flat``), a tab dragged along the one bar, let go before the tab now at ``at``
 * (counted without it): it goes there — into the group of the tab it lands next to.
 */
export function moveFlat(layout: Layout, file: string, at: number, files: string[]): Layout {
  const others = layout.groups.flatMap((g, gi) => g.tabs.filter((f) => f !== file).map((f) => ({ f, gi })));
  if (!others.length) return layout;
  const next = others[Math.min(at, others.length - 1)];
  const group = next.gi;
  const inGroup = layout.groups[group].tabs.filter((f) => f !== file);
  const place = at < others.length ? inGroup.indexOf(next.f) : inGroup.length;
  return moveTo(layout, file, group, files, place);
}

/** The groups' shares of the width, as they are now on screen, with the border between two dragged. */
export function resize(layout: Layout, widths: number[], left: number, x: number): Layout {
  const pair = widths[left] + widths[left + 1];
  const w = Math.min(pair - 160, Math.max(160, x));
  const sizes = widths.map((v, i) => (i === left ? w : i === left + 1 ? pair - w : v));
  const total = sizes.reduce((a, b) => a + b, 0) || 1;
  return { ...layout, groups: layout.groups.map((g, i) => ({ ...g, size: (sizes[i] / total) * sizes.length })) };
}
