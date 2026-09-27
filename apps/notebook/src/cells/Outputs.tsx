import type { Output } from "../types";
import { Markdown } from "./Markdown";

export function Outputs({ outputs }: { outputs: Output[] }) {
  if (!outputs.length) return null;
  return (
    <div className="outputs">
      {outputs.map((o, i) => {
        switch (o.type) {
          case "svg":
            // SVG produced by our own renderer, from this notebook's own code.
            return <div key={i} className="output-svg" dangerouslySetInnerHTML={{ __html: o.data }} />;
          case "markdown":
            return <Markdown key={i} source={o.data} />;
          case "error":
            return <pre key={i} className="output-error">{o.data}</pre>;
          case "warning":
            return <div key={i} className="output-warning">⚠ {o.data}</div>;
          default:
            return <pre key={i} className="output-text">{o.data}</pre>;
        }
      })}
    </div>
  );
}
