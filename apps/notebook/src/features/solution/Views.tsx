// What went wrong, and a worked solution, on the page. An issue is said in the page's language
// (Markdown, math in KaTeX); Python's own errors stay in its words, as they came.
import type { Failure, Steps } from "@/shared/model/issues";
import { Markdown } from "@/shared/ui/Markdown";
import { cn } from "@/shared/lib/cn";
import { useSay } from "./say";

const box = "m-0 px-2.5 py-1.5 rounded-md text-[16px]";
const look = {
  error: "overflow-x-auto whitespace-pre-wrap bg-err-bg text-danger",
  warning: "bg-warn-bg text-warn",
};

/** An error or a warning in its box. data-output (for the tests): which, or `issue` for one shown
 *  on purpose — display(err) — rather than a cell that failed. */
export function FailureBox({ failure, kind = "error", shown, className }: {
  failure: Failure; kind?: "error" | "warning"; shown?: boolean; className?: string;
}) {
  const output = shown ? "issue" : kind;
  const say = useSay();
  const mark = kind === "warning" ? "⚠ " : "";
  if (failure.issue)
    return (
      <div data-output={output} className={cn(box, look[kind], "whitespace-normal", className)}>
        <Markdown source={mark + say.line(failure.line) + say.issue(failure.issue)} />
      </div>
    );
  const Tag = kind === "error" ? "pre" : "div";
  return <Tag data-output={output} className={cn(box, look[kind], className)}>{mark}{say.line(failure.line)}{failure.data}</Tag>;
}

export function Solution({ steps }: { steps: Steps }) {
  return <Markdown source={useSay().steps(steps)} />;
}
