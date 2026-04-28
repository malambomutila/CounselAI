import { useState } from "react";
import { Markdown } from "./Markdown";

export type AgentKey = "plaintiff" | "defense" | "expert" | "judge";

interface AgentPanelProps {
  agent: AgentKey;
  title: string;
  body: string;
  placeholder?: string;
  /** Hides the refine input when false (e.g. before phase 2 for the Judge). */
  refinable?: boolean;
  /** Disables the refine input (e.g. while a pipeline run is in flight). */
  busy?: boolean;
  onRefine?: (text: string) => void;
}

export function AgentPanel({
  agent,
  title,
  body,
  placeholder,
  refinable = true,
  busy = false,
  onRefine,
}: AgentPanelProps) {
  const [draft, setDraft] = useState("");

  const submit = () => {
    const v = draft.trim();
    if (!v || busy || !onRefine) return;
    onRefine(v);
    setDraft("");
  };

  const isPlaceholder = !body || body === placeholder;
  const display = body || placeholder || "";

  return (
    <div className="agent-card" data-agent={agent}>
      <div className="agent-header">
        <h3>{title}</h3>
      </div>
      <Markdown source={display} placeholder={isPlaceholder} />
      {refinable && (
        <div className="agent-footer">
          <input
            type="text"
            placeholder="Refine argument…"
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
