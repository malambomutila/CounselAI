import { SignOutButton, useUser } from "@clerk/nextjs";
import { useEffect, useRef, useState } from "react";

// Top-right avatar button. Click → reveals a small dropdown showing the
// signed-in email and a Sign out action. Closes on outside click or Esc.
//
// We render the avatar as a button (not a div) so it's keyboard-focusable;
// the dropdown is positioned absolutely under it. Clerk's UserButton
// already does something similar, but it ships with its own appearance
// system that fights our editorial theme — easier to roll our own.
export function UserMenu() {
  const { user, isLoaded } = useUser();
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (!wrapRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  if (!isLoaded) {
    return <div className="user-menu-avatar is-loading">·</div>;
  }

  const email = user?.primaryEmailAddress?.emailAddress ?? "";
  const name = user?.fullName ?? "";
  const label = email || name || "Signed in";
  const initial = (label || "?")[0].toUpperCase();

  return (
    <div ref={wrapRef} className="user-menu">
      <button
        type="button"
        className="user-menu-avatar"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`Open account menu — ${label}`}
        title={label}
        onClick={() => setOpen((v) => !v)}
      >
        {user?.hasImage && user.imageUrl ? (
          // Clerk gives users a profile image when they upload one.
          // eslint-disable-next-line @next/next/no-img-element
          <img src={user.imageUrl} alt="" className="user-menu-avatar-img" />
        ) : (
          initial
        )}
      </button>

      {open && (
        <div className="user-menu-dropdown" role="menu">
          <div className="user-menu-header">
            <div className="user-menu-name" title={label}>{label}</div>
            <div className="user-menu-sub">Signed in</div>
          </div>
          <SignOutButton redirectUrl="/">
            <button type="button" className="user-menu-item" role="menuitem">
              <span aria-hidden="true">⎋</span>
              Sign out
            </button>
          </SignOutButton>
        </div>
      )}
    </div>
  );
}
