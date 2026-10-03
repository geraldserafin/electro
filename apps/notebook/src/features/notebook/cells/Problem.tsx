// A drawing as a problem is set (schematic/sought.ts): its data apart from it — each element's value, each
// mark's — and what is sought; after a run, what that came to. The drawing itself only names things.
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { askable, givenBy, Name, named, nameOf, sought, unitOf } from "@/features/schematic";
import { cn } from "@/shared/lib/cn";
import type { SchematicData, SymbolLibrary } from "@/shared/model/types";

const field =
  "h-8 px-2 rounded-md border border-transparent bg-hover text-[14px] tabular-nums focus:bg-paper focus:outline-2 focus:outline-accent-soft";
const row = "grid grid-cols-[4.5rem_minmax(0,9rem)_2rem] items-center gap-2";

const KINDS = ["U", "I", "P", "value", "mark", "R"] as const;
type Kind = (typeof KINDS)[number];

/** The data: an input per element (empty: unknown), then what is sought, more added from the lists. */
export function DataTab({
  schematic,
  library,
  onChange,
}: {
  schematic: SchematicData;
  library: SymbolLibrary;
  onChange: (schematic: SchematicData) => void;
}) {
  const { t } = useTranslation("notebook");
  const given = schematic.elements.filter(givenBy);
  const asked = new Set(schematic.find ?? []);
  const options = askable(schematic, library);
  const [kind, setKind] = useState<Kind>("U");
  const [of, setOf] = useState("");
  const [to, setTo] = useState("");
  const choices =
    kind === "value" ? options.valued : kind === "mark" || kind === "R" ? options.points : options.elements;
  const first = choices.some((e) => e.id === of) ? of : (choices[0]?.id ?? "");
  const second =
    options.points.find((e) => e.id === to && e.id !== first)?.id ??
    options.points.find((e) => e.id !== first)?.id ??
    "";
  const key = kind === "R" ? `R:${first}:${second}` : `${kind}:${first}`;
  const ready = !!first && (kind !== "R" || !!second) && !sought(schematic).includes(key);
  const setValue = (id: string, value: string) =>
    onChange({
      ...schematic,
      elements: schematic.elements.map((e) => (e.id === id ? { ...e, value: value.trim() === "" ? null : value } : e)),
    });
  if (!schematic.elements.length) return <p className="m-3 text-muted">{t("data.none")}</p>;
  return (
    <div className="flex flex-wrap gap-x-10 gap-y-4 px-3 py-2.5 text-[14px]">
      <section className="grid gap-1.5 content-start">
        <h4 className="m-0 text-[13px] font-normal text-muted">{t("data.given")}</h4>
        {given.map((e) => (
          <label key={e.id} className={row}>
            <span className="font-medium">
              <Name text={nameOf(e)} />
            </span>
            <input
              className={field}
              value={e.value ?? ""}
              inputMode="decimal"
              spellCheck={false}
              placeholder="?"
              aria-label={nameOf(e)}
              onChange={(event) => setValue(e.id, event.target.value)}
            />
            <span className="text-muted">{unitOf(e)}</span>
          </label>
        ))}
      </section>
      <section className="grid gap-1.5 content-start">
        <h4 className="m-0 text-[13px] font-normal text-muted">{t("data.sought")}</h4>
        {sought(schematic).map((k) => (
          <div key={k} className="flex items-center gap-2 min-h-8">
            <span className="font-medium min-w-12">
              <Name text={named(schematic, k) ?? k} />
            </span>
            {asked.has(k) ? (
              <button
                type="button"
                className="grid place-items-center size-7 rounded-md text-muted hover:bg-err-bg hover:text-danger"
                title={t("data.remove")}
                aria-label={t("data.remove")}
                onClick={() => onChange({ ...schematic, find: (schematic.find ?? []).filter((x) => x !== k) })}
              >
                ×
              </button>
            ) : (
              <span className="text-muted text-[13px]">{t("data.unknown")}</span>
            )}
          </div>
        ))}
        {/* another: what, of what (two points: between them) */}
        <div className="flex flex-wrap items-center gap-1.5 mt-1">
          <select
            className={field}
            value={kind}
            aria-label={t("data.what")}
            onChange={(event) => setKind(event.target.value as Kind)}
          >
            {KINDS.map((k) => (
              <option key={k} value={k}>
                {t(`data.kinds.${k}`)}
              </option>
            ))}
          </select>
          {kind === "R" && options.points.length < 2 ? (
            <span className="text-muted text-[13px] max-w-60">{t("data.needPoints")}</span>
          ) : (
            <>
              <select
                className={field}
                value={first}
                aria-label={kind === "R" ? t("data.from") : t("data.of")}
                onChange={(event) => setOf(event.target.value)}
              >
                {choices.map((e) => (
                  <option key={e.id} value={e.id}>
                    {nameOf(e)}
                  </option>
                ))}
              </select>
              {kind === "R" && (
                <select
                  className={field}
                  value={second}
                  aria-label={t("data.to")}
                  onChange={(event) => setTo(event.target.value)}
                >
                  {options.points
                    .filter((e) => e.id !== first)
                    .map((e) => (
                      <option key={e.id} value={e.id}>
                        {nameOf(e)}
                      </option>
                    ))}
                </select>
              )}
              <button
                type="button"
                className="h-8 px-3 rounded-md bg-hover hover:bg-selected disabled:opacity-40"
                disabled={!ready}
                onClick={() => onChange({ ...schematic, find: [...(schematic.find ?? []), key] })}
              >
                {t("data.add")}
              </button>
            </>
          )}
        </div>
      </section>
    </div>
  );
}

/** What the sought came to (a run's), each by its name. */
export function FoundTab({
  schematic,
  found,
  stale,
}: {
  schematic: SchematicData;
  found: Record<string, string | null>;
  stale: boolean;
}) {
  const { t } = useTranslation("notebook");
  const keys = sought(schematic).filter((k) => k in found);
  if (!keys.length) return <p className="m-3 text-muted">{t("results.none")}</p>;
  return (
    <dl
      aria-label={t("results.label")}
      data-stale={stale || undefined}
      className="m-0 px-3 py-2.5 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-[16px] tabular-nums transition-opacity duration-150 data-stale:opacity-45"
    >
      {keys.map((k) => (
        <div key={k} className="contents">
          <dt className="font-medium">
            <Name text={named(schematic, k) ?? k} />
          </dt>
          <dd className={cn("m-0", found[k] ? "text-accent font-semibold" : "text-muted")}>
            {found[k] ? `= ${found[k]}` : t("results.notFound")}
          </dd>
        </div>
      ))}
    </dl>
  );
}
