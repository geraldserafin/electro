// What the run found, element by element. data-stale: from an older drawing (the run button is on again).
import { useTranslation } from "react-i18next";
import type { ElementResult } from "@/shared/model/types";

/** "R_1" → R with a subscript 1. */
function Name({ id }: { id: string }) {
  const [base, ...sub] = id.split("_");
  return <>{base}{sub.length > 0 && <sub className="text-[0.72em]">{sub.join(",")}</sub>}</>;
}

// alignment per cell (the names left, the numbers right): two text-* on one element would fight
const cell = "px-4 whitespace-nowrap";

export function ResultsTable({ results, stale }: { results: Record<string, ElementResult>; stale: boolean }) {
  const { t } = useTranslation("notebook");
  const th = `${cell} py-2 bg-hover text-muted text-[13px] font-medium`;
  const td = `${cell} py-1.75 border-t border-line`;
  const num = { th: `${th} text-right`, td: `${td} text-right` };
  return (
    <table aria-label={t("results.label")} data-stale={stale || undefined}
           className="mt-3 border-separate border-spacing-0 border border-line rounded-[10px] overflow-hidden text-[16px] tabular-nums
                      transition-opacity duration-150 data-stale:opacity-45 [&_tbody_tr:hover_td]:bg-hover">
      <thead>
        <tr>
          <th className={`${th} text-left`}>{t("results.element")}</th><th className={num.th}>{t("results.value")}</th>
          <th className={num.th}>{t("results.voltage")}</th><th className={num.th}>{t("results.current")}</th><th className={num.th}>{t("results.power")}</th>
        </tr>
      </thead>
      <tbody>
        {Object.entries(results).map(([id, r]) => (
          <tr key={id}>
            <td className={`${td} text-left font-medium`}><Name id={id} /></td>
            <td className={`${num.td} ${r.solved ? "text-accent font-semibold" : ""}`}>{r.value || "—"}</td>
            <td className={num.td}>{r.U ?? "—"}</td>
            <td className={num.td}>{r.I ?? "—"}</td>
            <td className={num.td}>{r.P ?? "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
