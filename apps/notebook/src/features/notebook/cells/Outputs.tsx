// What a code cell printed. data-output: which kind (the tests find them by it).

import { FailureBox, Solution } from "@/features/solution";
import { cn } from "@/shared/lib/cn";
import type { Output } from "@/shared/model/types";
import { Markdown } from "@/shared/ui/Markdown";

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
