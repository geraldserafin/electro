import { memo } from "react";
import ReactMarkdown from "react-markdown";
import rehypeKatex from "rehype-katex";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import "./Markdown.css";

const remarkPlugins = [remarkGfm, remarkMath];
const rehypePlugins = [rehypeKatex];

/**
 * Markdown (with tables) and $math$ — used for text cells and for rich outputs (e.g. steps()).
 * Parsed (and its math typeset) again only when its text changes, not whenever the note is.
 */
export const Markdown = memo(function Markdown({ source }: { source: string }) {
  return (
    <div className="markdown">
      <ReactMarkdown remarkPlugins={remarkPlugins} rehypePlugins={rehypePlugins}>
        {source}
      </ReactMarkdown>
    </div>
  );
});
