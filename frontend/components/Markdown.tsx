import ReactMarkdown from "react-markdown";
import remarkBreaks from "remark-breaks";
import remarkGfm from "remark-gfm";
import rehypeSanitize, { defaultSchema } from "rehype-sanitize";

// Extend the default schema to allow markdown-generated links and standard attributes
// while blocking <script>, <iframe>, event handlers, and javascript: URLs.
const sanitizeSchema = {
  ...defaultSchema,
  attributes: {
    ...defaultSchema.attributes,
    a: [["href", /^(?!javascript:)/i], "title", "target", "rel"],
    "*": ["className"],
  },
};

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
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkBreaks]}
        rehypePlugins={[[rehypeSanitize, sanitizeSchema]]}
        disallowedElements={["script", "iframe", "object", "embed"]}
        unwrapDisallowed
      >
        {source || ""}
      </ReactMarkdown>
    </div>
  );
}
