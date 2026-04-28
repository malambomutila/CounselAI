import { SignOutButton, useUser } from "@clerk/nextjs";
import type { ConversationHeader } from "@/lib/api";

interface SidebarProps {
  history: ConversationHeader[];
  activeId: string;
  onSelect: (convId: string) => void;
  onRefresh: () => void;
  onNewCase: () => void;
}

export function Sidebar({
  history,
  activeId,
  onSelect,
  onRefresh,
  onNewCase,
}: SidebarProps) {
  const { user } = useUser();
  const email = user?.primaryEmailAddress?.emailAddress ?? "";
  const name = user?.fullName ?? "";
  const label = email || name || "Signed in";
  const initial = (label || "?")[0].toUpperCase();

  return (
    <aside className="sidebar w-[260px] flex-shrink-0 px-5 py-7 flex flex-col gap-4">
      <header>
        <h1 className="font-display font-bold text-[22px] tracking-[-0.02em] leading-none mb-1">
          CounselAI
        </h1>
        <p className="text-[9.5px] uppercase tracking-[0.18em] text-slate-400 font-semibold">
          Multi-agent legal intelligence
        </p>
      </header>

      <div className="profile-chip">
        <div className="profile-avatar">{initial}</div>
        <div className="min-w-0 flex flex-col leading-tight">
          <div className="profile-name" title={label}>{label}</div>
          <div className="profile-sub">Signed in</div>
        </div>
      </div>

      <SignOutButton redirectUrl="/">
        <button type="button" className="signout-btn">
          <span aria-hidden="true">⎋</span>
          Sign out
        </button>
      </SignOutButton>

      <button
        type="button"
        className="cta-primary mt-2"
        onClick={onNewCase}
      >
        New case analysis
      </button>

      <div className="section-label mt-3">Past cases</div>
      <div className="flex flex-col gap-2 max-h-[60vh] overflow-y-auto pr-1">
        {history.length === 0 && (
          <p className="text-xs text-slate-400 italic px-1">
            No cases yet. Run an analysis to populate this list.
          </p>
        )}
        {history.map((c) => (
          <div
            key={c.conversation_id}
            className={`history-row ${c.conversation_id === activeId ? "is-active" : ""}`}
            onClick={() => onSelect(c.conversation_id)}
          >
            <div className="history-id">#{c.conversation_id.slice(0, 6)}</div>
            <div className="history-title">{c.title || "Untitled case"}</div>
            <div className="history-meta">
              {c.legal_area} · {(c.updated_at || "").slice(0, 10)}
            </div>
          </div>
        ))}
      </div>

      <button
        type="button"
        onClick={onRefresh}
        className="text-xs text-ink-subtle underline hover:text-primary self-start mt-1"
      >
        Refresh
      </button>
    </aside>
  );
}
