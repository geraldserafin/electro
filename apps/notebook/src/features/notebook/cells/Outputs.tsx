// What a code cell printed. data-output: which kind (the tests find them by it).

import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { FailureBox, Solution } from "@/features/solution";
import { cn } from "@/shared/lib/cn";
import type { Output } from "@/shared/model/types";
import { Markdown } from "@/shared/ui/Markdown";
import { isRight, parseAnswer } from "./task";

const box = "m-0 px-2.5 py-1.5 rounded-md text-[16px]";

export function Outputs({ outputs }: { outputs: Output[] }) {
  if (!outputs.length) return null;
  return (
    <div data-outputs className="grid gap-2">
      {outputs.map((o, i) => {
        switch (o.type) {
          case "svg":
            // SVG produced by our own renderer, from this notebook's own code.
            return (
              <div
                key={i}
                data-output="svg"
                className="overflow-x-auto [&_svg]:max-w-full [&_svg]:h-auto"
                dangerouslySetInnerHTML={{ __html: o.data }}
              />
            );
          case "markdown":
            return <Markdown key={i} source={o.data} />;
          case "solution":
            return <Solution key={i} steps={o.data} />;
          case "error":
          case "warning":
            return <FailureBox key={i} failure={o} kind={o.type} />;
          case "issue":
            return <FailureBox key={i} failure={o} kind={o.kind} shown />;
          case "task":
            return <TaskBox key={i} task={o} />;
          default:
            return (
              <pre key={i} data-output="text" className={cn(box, "overflow-x-auto whitespace-pre-wrap font-mono")}>
                {o.data}
              </pre>
            );
        }
      })}
    </div>
  );
}

/** A task: its prompt, and a field whose answer is checked in the page (against the hashes). */
function TaskBox({ task }: { task: Extract<Output, { type: "task" }> }) {
  const { t } = useTranslation("notebook");
  const [answer, setAnswer] = useState("");
  const [verdict, setVerdict] = useState<"right" | "wrong" | "unreadable" | null>(null);
  const check = async (e: FormEvent) => {
    e.preventDefault();
    const value = parseAnswer(answer);
    if (value === null) return setVerdict("unreadable");
    setVerdict((await isRight(task.quantity, value, task.tol, task.hashes)) ? "right" : "wrong");
  };
  return (
    <form data-output="task" onSubmit={check} className="grid gap-2 rounded-lg border border-line p-3">
      {task.prompt && <Markdown source={task.prompt} />}
      <div className="flex flex-wrap items-center gap-2">
        <Markdown source={`$${task.tex}${task.amplitude ? `\\ (${t("task.amplitude")})` : ""} =$`} />
        <input
          className="w-36 rounded-md border border-line bg-board px-2 py-1 text-[15px]"
          value={answer}
          aria-label={t("task.answer")}
          placeholder={t("task.answer")}
          onChange={(e) => {
            setAnswer(e.target.value);
            setVerdict(null);
          }}
        />
        <span className="text-muted">{task.unit}</span>
        <button
          type="submit"
          className="rounded-md bg-primary px-3 py-1 text-[14px] font-medium text-on-primary hover:bg-primary-hover"
        >
          {t("task.check")}
        </button>
        {verdict && (
          <span role="status" className={cn("text-[14px]", verdict === "right" ? "text-ok" : "text-danger")}>
            {t(`task.${verdict}`)}
          </span>
        )}
      </div>
    </form>
  );
}
