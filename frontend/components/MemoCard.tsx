import { useState } from "react";
import { Markdown } from "./Markdown";

interface MemoCardProps {
  body: string;
  busy: boolean;
  refinable: boolean;
  onRefine: (text: string) => void;
}

export function MemoCard({ body, busy, refinable, onRefine }: MemoCardProps) {
  const [draft, setDraft] = useState("");
  const submit = () => {
    const v = draft.trim();
    if (!v || busy || !refinable) return;
    onRefine(v);
    setDraft("");
  };
  const isPlaceholder = body.startsWith("_") && body.endsWith("_");
  return (
    <div className="memo-card">
      <h3>Strategic Case Memo</h3>
      <Markdown source={body} placeholder={isPlaceholder} />
      {refinable && (
        <div className="agent-footer rounded-sm mt-4">
          <input
            type="text"
            placeholder="Refine the strategic memo…"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") submit();
            }}
            disabled={busy}
          />
          <button type="button" onClick={submit} disabled={busy || !draft.trim()}>
            Send
          </button>
        </div>
      )}
    </div>
  );
}
