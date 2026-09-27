import ReactMarkdown from "react-markdown";
import rehypeKatex from "rehype-katex";
import remarkMath from "remark-math";

/** Markdown with $math$ — used for text cells and for rich outputs (e.g. steps()). */
export function Markdown({ source }: { source: string }) {
  return (
    <div className="markdown">
      <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
        {source}
      </ReactMarkdown>
    </div>
  );
}
