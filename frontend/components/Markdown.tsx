import ReactMarkdown from "react-markdown";
import remarkBreaks from "remark-breaks";
import remarkGfm from "remark-gfm";

interface MarkdownProps {
  source: string;
  /** When true, paint as muted italic placeholder (used for empty agent panels). */
  placeholder?: boolean;
  className?: string;
}

export function Markdown({ source, placeholder, className }: MarkdownProps) {
  const cls = [
    "agent-body",
    placeholder ? "is-placeholder" : "",
    className ?? "",
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <div className={cls}>
      <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}>
        {source || (placeholder ? "" : "")}
      </ReactMarkdown>
    </div>
  );
}
