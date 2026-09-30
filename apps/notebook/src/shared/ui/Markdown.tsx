import { memo, type ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import rehypeKatex from "rehype-katex";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import "./Markdown.css";

const remarkPlugins = [remarkGfm, remarkMath];
const rehypePlugins = [rehypeKatex];
// inside something that is a link already (a note's card): links as plain text
const noLinks = { a: ({ children }: { children?: ReactNode }) => <span>{children}</span> };

/**
 * Markdown (with tables) and $math$ — used for text cells and for rich outputs (e.g. steps()).
 * Parsed (and its math typeset) again only when its text changes, not whenever the note is.
 */
export const Markdown = memo(function Markdown({ source, links = true }: { source: string; links?: boolean }) {
  return (
    <div className="markdown">
      <ReactMarkdown
        remarkPlugins={remarkPlugins}
        rehypePlugins={rehypePlugins}
        components={links ? undefined : noLinks}
      >
        {source}
      </ReactMarkdown>
    </div>
  );
});
