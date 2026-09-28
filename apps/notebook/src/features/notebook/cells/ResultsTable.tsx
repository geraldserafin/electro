// What the run found, element by element. data-stale: from an older drawing (the run button is on again).
import { useTranslation } from "react-i18next";
import type { ElementResult } from "@/shared/model/types";
import { cn } from "@/shared/lib/cn";

/** "R_1" → R with a subscript 1. */
function Name({ id }: { id: string }) {
  const [base, ...sub] = id.split("_");
  return <>{base}{sub.length > 0 && <sub className="static align-sub text-[0.72em] leading-[inherit]">{sub.join(",")}</sub>}</>;
}

const cell = "px-4 text-right whitespace-nowrap"; // the numbers right, the names (cn: text-left) left

export function ResultsTable({ results, stale }: { results: Record<string, ElementResult>; stale: boolean }) {
  const { t } = useTranslation("notebook");
  const th = `${cell} py-2 bg-hover text-muted text-[13px] font-medium`;
  const td = `${cell} py-1.75 border-t border-line`;
  return (
    <table aria-label={t("results.label")} data-stale={stale || undefined}
           className="mt-3 border-separate border-spacing-0 border border-line rounded-[10px] overflow-hidden text-[16px] tabular-nums
                      transition-opacity duration-150 data-stale:opacity-45 [&_tbody_tr:hover_td]:bg-hover">
      <thead>
        <tr>
          <th className={cn(th, "text-left")}>{t("results.element")}</th><th className={th}>{t("results.value")}</th>
          <th className={th}>{t("results.voltage")}</th><th className={th}>{t("results.current")}</th><th className={th}>{t("results.power")}</th>
        </tr>
      </thead>
      <tbody>
        {Object.entries(results).map(([id, r]) => (
          <tr key={id}>
            <td className={cn(td, "text-left font-medium")}><Name id={id} /></td>
            <td className={cn(td, r.solved && "text-accent font-semibold")}>{r.value || "—"}</td>
            <td className={td}>{r.U ?? "—"}</td>
            <td className={td}>{r.I ?? "—"}</td>
            <td className={td}>{r.P ?? "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
