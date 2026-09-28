// What a code cell printed. data-output: which kind (the tests find them by it).
import type { Output } from "@/shared/model/types";
import { Markdown } from "@/shared/ui/Markdown";
import { cn } from "@/shared/lib/cn";

const box = "m-0 px-2.5 py-1.5 rounded-md text-[16px]";
export const errorBox = cn(box, "overflow-x-auto whitespace-pre-wrap bg-err-bg text-danger");

export function Outputs({ outputs }: { outputs: Output[] }) {
  if (!outputs.length) return null;
  return (
    <div data-outputs className="mt-2 grid gap-2">
      {outputs.map((o, i) => {
        switch (o.type) {
          case "svg":
            // SVG produced by our own renderer, from this notebook's own code.
            return <div key={i} data-output="svg" className="overflow-x-auto [&_svg]:max-w-full [&_svg]:h-auto"
                        dangerouslySetInnerHTML={{ __html: o.data }} />;
          case "markdown":
            return <Markdown key={i} source={o.data} />;
          case "error":
            return <pre key={i} data-output="error" className={errorBox}>{o.data}</pre>;
          case "warning":
            return <div key={i} data-output="warning" className={cn(box, "bg-warn-bg text-warn")}>⚠ {o.data}</div>;
          default:
            return <pre key={i} data-output="text" className={cn(box, "overflow-x-auto whitespace-pre-wrap font-mono")}>{o.data}</pre>;
        }
      })}
    </div>
  );
}
