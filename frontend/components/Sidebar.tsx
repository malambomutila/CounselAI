import type { ConversationHeader } from "@/lib/api";

interface SidebarProps {
  history: ConversationHeader[];
  activeId: string;
  onSelect: (convId: string) => void;
  /** Kept for compatibility with the parent's API; the visible Refresh
   * button is gone, but the parent still re-fetches automatically on
   * every pipeline ``done`` event. */
  onRefresh: () => void;
  onNewCase: () => void;
}

// Inline SVGs — small enough to live alongside the component and avoid
// the dep cost of lucide-react. Stroke uses currentColor so they pick up
// the surrounding text colour transitions.
function PlusIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
         stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
      <line x1="12" y1="5" x2="12" y2="19" />
      <line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  );
}

function ClockIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
         stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </svg>
  );
}

function ScaleIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
         stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 3v18" />
      <path d="M5 21h14" />
      <path d="M5 7l-3 6c0 1.7 1.3 3 3 3s3-1.3 3-3l-3-6z" />
      <path d="M19 7l-3 6c0 1.7 1.3 3 3 3s3-1.3 3-3l-3-6z" />
      <path d="M5 7l7-3 7 3" />
    </svg>
  );
}

export function Sidebar({
  history,
  activeId,
  onSelect,
  onNewCase,
}: SidebarProps) {
  return (
    // The sidebar is collapsed by default and expands on :hover.
    // ``group`` lets descendant utility classes react to that hover.
    <aside className="sidebar group">
      <header className="sb-brand">
        <div className="sb-brand-mark" aria-hidden="true">
          <ScaleIcon />
        </div>
        <div className="sb-brand-text">
          <h1>MoootCourt</h1>
        </div>
      </header>

      <button
        type="button"
        className="sb-action"
        onClick={onNewCase}
        title="New case analysis"
        aria-label="New case analysis"
      >
        <span className="sb-action-icon"><PlusIcon /></span>
        <span className="sb-action-label">New case</span>
      </button>

      <div className="sb-section-label">
        <span className="sb-section-icon" aria-hidden="true"><ClockIcon /></span>
        <span className="sb-section-text">Past cases</span>
      </div>

      <div className="sb-history">
        {history.length === 0 && (
          <p className="sb-empty">No cases yet.</p>
        )}
        {history.map((c) => {
          const isActive = c.conversation_id === activeId;
          const initial = (c.title || "?")[0].toUpperCase();
          return (
            <button
              key={c.conversation_id}
              type="button"
              className={`sb-row ${isActive ? "is-active" : ""}`}
              onClick={() => onSelect(c.conversation_id)}
              title={c.title || "Untitled case"}
            >
              <span className="sb-row-pip" aria-hidden="true">{initial}</span>
              <span className="sb-row-text">
                <span className="sb-row-title">{c.title || "Untitled case"}</span>
                <span className="sb-row-meta">
                  {c.legal_area}
                  {c.updated_at ? ` · ${c.updated_at.slice(0, 10)}` : ""}
                </span>
              </span>
            </button>
          );
        })}
      </div>
    </aside>
  );
}
