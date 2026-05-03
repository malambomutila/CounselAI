import Head from "next/head";
import Link from "next/link";
import dynamic from "next/dynamic";
import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/router";
import type { GetServerSideProps } from "next";
import { SignInButton, SignedIn, SignedOut, useAuth } from "@clerk/nextjs";

const TOTAL = 3;

// ── Agent card data ─────────────────────────────────────────────────────────
const AGENTS = [
  {
    name: "Plaintiff's Counsel",
    desc: "Builds the strongest case for the claimant's position",
    borderColor: "var(--primary)",
    bg: "linear-gradient(90deg, var(--primary-tint), #ffffff 50%)",
  },
  {
    name: "Defense Counsel",
    desc: "Constructs the sharpest counter to every argument made",
    borderColor: "#0F52FF",
    bg: "linear-gradient(90deg, rgba(15, 82, 255, 0.08), #ffffff 50%)",
  },
  {
    name: "Expert Witness",
    desc: "Provides technical, domain, and evidentiary analysis",
    borderColor: "var(--amber)",
    bg: "linear-gradient(90deg, var(--amber-tint), #ffffff 50%)",
  },
  {
    name: "Judge",
    desc: "Weighs both sides and delivers an honest assessment",
    borderColor: "var(--rose)",
    bg: "linear-gradient(90deg, var(--rose-tint), #ffffff 50%)",
  },
  {
    name: "Legal Strategist",
    desc: "Synthesises all outputs into the clearest path forward",
    borderColor: "#334155",
    bg: "linear-gradient(90deg, var(--slate-tint), #ffffff 50%)",
  },
];

// ── B2B cards ────────────────────────────────────────────────────────────────
const B2B_CARDS = [
  {
    num: "01",
    title: "One Session, Five Specialists",
    body: "Every angle your opposing counsel could take is already in the room. You see the weaknesses in your own position before the other side does, and you have time to address them.",
  },
  {
    num: "02",
    title: "New Evidence Changes Everything, Instantly",
    body: "Drop a new piece of information into the session and watch plaintiff, defense, and expert simultaneously recalibrate their arguments around it. Context never resets.",
  },
  {
    num: "03",
    title: "A Full Case Record, Always Saved",
    body: "Every analysis, follow up question, and agent response is stored and reloadable. Your junior associates can pick up exactly where the partner left off, with nothing lost between sessions.",
  },
];

// ── B2C points ───────────────────────────────────────────────────────────────
const B2C_LEFT = [
  { strong: "Your strongest arguments,", rest: " articulated clearly so you know exactly what position to stand on" },
  { strong: "The opposition's best moves,", rest: " so nothing the other side says in a meeting or courtroom catches you off guard" },
  { strong: "An honest judicial assessment", rest: " of how strong your case actually is, not just the version that makes you feel better" },
  { strong: "A concrete path forward", rest: " from a strategist who has read everything the other agents said before recommending anything" },
];

const B2C_RIGHT = [
  { strong: "", rest: "Describe your situation in plain language. No legal terminology required. The agents understand context, not just keywords." },
  { strong: "", rest: "Choose your jurisdiction and legal area. MoootCourt adjusts its reasoning to the rules that actually apply to your case." },
  { strong: "", rest: "Ask follow up questions to any individual agent. If the judge's assessment surprised you, ask them to explain their reasoning directly." },
  { strong: "", rest: "Come back to the session any time. Your full conversation history is saved, so you can continue as your situation develops." },
];

// ── Shared style objects ─────────────────────────────────────────────────────
const card: React.CSSProperties = {
  background: "#ffffff",
  border: "1px solid var(--hairline)",
  borderRadius: 10,
  boxShadow: "0 1px 2px rgba(15,23,42,0.04), 0 4px 12px rgba(15,23,42,0.04)",
};

const eyebrowStyle = (color: string): React.CSSProperties => ({
  fontFamily: "'Inter', sans-serif",
  fontSize: 10.5,
  fontWeight: 700,
  letterSpacing: "0.14em",
  textTransform: "uppercase",
  color,
  marginBottom: 14,
  display: "block",
});

function Landing() {
  const router = useRouter();
  const { isSignedIn, isLoaded } = useAuth();
  const [slide, setSlide] = useState(0);

  useEffect(() => {
    if (isLoaded && isSignedIn) router.replace("/app");
  }, [isLoaded, isSignedIn, router]);

  const go = useCallback((dir: number) => {
    setSlide(s => Math.max(0, Math.min(TOTAL - 1, s + dir)));
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight" || e.key === "ArrowDown") go(1);
      if (e.key === "ArrowLeft"  || e.key === "ArrowUp")   go(-1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [go]);

  const slideStyle = (n: number): React.CSSProperties => ({
    position: "absolute",
    inset: 0,
    display: "flex",
    flexDirection: "column",
    justifyContent: "center",
    alignItems: "center",
    padding: "40px 72px",
    opacity: slide === n ? 1 : 0,
    pointerEvents: slide === n ? "all" : "none",
    transition: "opacity 0.4s ease",
    background: "var(--canvas)",
  });

  const SignInBtn = () => (
    <SignedOut>
      <SignInButton mode="modal">
        <button className="cta-primary" style={{ fontSize: 14, padding: "9px 24px" }}>
          Sign in
        </button>
      </SignInButton>
    </SignedOut>
  );

  return (
    <>
      <Head>
        <title>MoootCourt</title>
      </Head>

      {/* ── Persistent nav ─────────────────────────────────────────────── */}
      <nav style={{
        position: "fixed",
        top: 0, left: 0, right: 0,
        height: 60,
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "0 36px",
        background: "#ffffff",
        borderBottom: "1px solid var(--hairline)",
        zIndex: 50,
        boxShadow: "0 1px 2px rgba(15,23,42,0.04)",
      }}>
        <span style={{
          fontFamily: "'Fraunces', Georgia, serif",
          fontVariationSettings: '"opsz" 144, "SOFT" 30, "wght" 700',
          fontSize: 22,
          letterSpacing: "-0.02em",
          color: "var(--ink)",
          userSelect: "none",
        }}>
          MoootCourt
        </span>

        <SignedOut>
          <SignInButton mode="modal">
            <button className="cta-primary" style={{ fontSize: 14, padding: "9px 24px" }}>
              Sign in
            </button>
          </SignInButton>
        </SignedOut>
        <SignedIn>
          <Link href="/app" className="cta-primary" style={{ fontSize: 14, padding: "9px 24px", textDecoration: "none", display: "inline-block" }}>
            Open app
          </Link>
        </SignedIn>
      </nav>

      {/* ── Slide container ────────────────────────────────────────────── */}
      <div style={{ position: "relative", height: "100vh", paddingTop: 60, overflow: "hidden", background: "var(--canvas)" }}>

        {/* ══ SLIDE 1: What is MoootCourt ══ */}
        <div style={slideStyle(0)}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 72, width: "100%", maxWidth: 1060, alignItems: "center" }}>

            {/* Left */}
            <div>
              <span style={eyebrowStyle("var(--primary)")}>AI Legal Analysis</span>
              <h1 style={{
                fontFamily: "'Fraunces', Georgia, serif",
                fontVariationSettings: '"opsz" 144, "SOFT" 40, "wght" 700',
                fontSize: 58,
                lineHeight: 1.0,
                letterSpacing: "-0.03em",
                color: "var(--ink)",
                marginBottom: 20,
              }}>
                Every angle.<br />
                <span style={{ color: "var(--primary)" }}>One session.</span>
              </h1>
              <p style={{ fontSize: 16.5, lineHeight: 1.7, color: "var(--ink-muted)", maxWidth: 420, marginBottom: 28 }}>
                MoootCourt puts five specialist AI agents on your case at once. Plaintiff,
                defense, expert witness, judge, and legal strategist each reason
                independently and in full context of each other. Add a new fact and watch
                every position update in real time.
              </p>
              <div style={{ borderTop: "1px solid var(--hairline)", paddingTop: 18 }}>
                <button
                  className="cta-primary"
                  style={{ fontSize: 14, padding: "9px 24px" }}
                  onClick={() => setSlide(1)}
                >
                  Learn More
                </button>
              </div>
            </div>

            {/* Right: agent cards */}
            <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
              {AGENTS.map(a => (
                <div key={a.name} style={{
                  ...card,
                  borderLeft: `4px solid ${a.borderColor}`,
                  background: a.bg,
                  padding: "13px 18px",
                }}>
                  <div style={{
                    fontFamily: "'Fraunces', serif",
                    fontVariationSettings: '"opsz" 30, "SOFT" 20, "wght" 600',
                    fontSize: 13.5,
                    color: "var(--ink)",
                    marginBottom: 3,
                  }}>
                    {a.name}
                  </div>
                  <div style={{ fontSize: 12, color: "var(--ink-muted)", lineHeight: 1.5 }}>
                    {a.desc}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* ══ SLIDE 2: Law Firms / B2B ══ */}
        <div style={slideStyle(1)}>
          <div style={{ width: "100%", maxWidth: 1060 }}>

            <div style={{ marginBottom: 36 }}>
              <span style={eyebrowStyle("var(--primary)")}>For Law Firms</span>
              <h2 style={{
                fontFamily: "'Fraunces', Georgia, serif",
                fontVariationSettings: '"opsz" 144, "SOFT" 40, "wght" 700',
                fontSize: 46,
                lineHeight: 1.05,
                letterSpacing: "-0.025em",
                color: "var(--ink)",
                maxWidth: 680,
                marginBottom: 14,
              }}>
                Case preparation used to<br />take days. Not anymore.
              </h2>
              <p style={{ fontSize: 15.5, color: "var(--ink-muted)", lineHeight: 1.65, maxWidth: 680 }}>
                When you use a general AI tool, you have to ask separately for the plaintiff
                angle, then the defense angle, then the expert view, each time starting a new
                conversation that has forgotten everything before it. MoootCourt runs all five
                perspectives simultaneously, keeps them in full context of each other, and
                lets you introduce new information mid session to see how every position shifts.
              </p>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16 }}>
              {B2B_CARDS.map(c => (
                <div key={c.num} style={{ ...card, padding: "24px 22px" }}>
                  <div style={{
                    fontFamily: "'Fraunces', serif",
                    fontVariationSettings: '"opsz" 30, "SOFT" 0, "wght" 700',
                    fontSize: 34,
                    color: "var(--primary)",
                    lineHeight: 1,
                    marginBottom: 12,
                    letterSpacing: "-0.03em",
                  }}>
                    {c.num}
                  </div>
                  <h3 style={{
                    fontFamily: "'Fraunces', serif",
                    fontVariationSettings: '"opsz" 30, "SOFT" 20, "wght" 600',
                    fontSize: 16,
                    color: "var(--ink)",
                    marginBottom: 9,
                    letterSpacing: "-0.01em",
                  }}>
                    {c.title}
                  </h3>
                  <p style={{ fontSize: 13.5, lineHeight: 1.65, color: "var(--ink-muted)" }}>
                    {c.body}
                  </p>
                </div>
              ))}
            </div>

          </div>
        </div>

        {/* ══ SLIDE 3: Everyone / B2C ══ */}
        <div style={slideStyle(2)}>
          <div style={{ width: "100%", maxWidth: 1060 }}>

            <div style={{ marginBottom: 32 }}>
              <span style={eyebrowStyle("#d97706")}>For Everyone</span>
              <h2 style={{
                fontFamily: "'Fraunces', Georgia, serif",
                fontVariationSettings: '"opsz" 144, "SOFT" 40, "wght" 700',
                fontSize: 46,
                lineHeight: 1.05,
                letterSpacing: "-0.025em",
                color: "var(--ink)",
                maxWidth: 660,
                marginBottom: 14,
              }}>
                The legal system was built<br />for lawyers. This is not.
              </h2>
              <p style={{ fontSize: 15.5, color: "var(--ink-muted)", lineHeight: 1.65, maxWidth: 660 }}>
                Most people facing a legal dispute have no idea what their options are,
                what the other side will argue, or what a judge is likely to think. Hiring
                a lawyer to find out costs money most people do not have. MoootCourt gives
                you the full picture before you make any decision.
              </p>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 18 }}>
              {/* Left block */}
              <div style={{ ...card, padding: "26px 24px" }}>
                <h3 style={{
                  fontFamily: "'Fraunces', serif",
                  fontVariationSettings: '"opsz" 60, "SOFT" 20, "wght" 600',
                  fontSize: 19,
                  color: "var(--ink)",
                  marginBottom: 16,
                  letterSpacing: "-0.01em",
                }}>
                  What you get from one session
                </h3>
                <ul style={{ listStyle: "none", display: "flex", flexDirection: "column", gap: 10 }}>
                  {B2C_LEFT.map((p, i) => (
                    <li key={i} style={{ fontSize: 13.5, lineHeight: 1.6, color: "var(--ink-muted)", paddingLeft: 16, position: "relative" }}>
                      <span style={{ position: "absolute", left: 0, top: 8, width: 5, height: 5, borderRadius: "50%", background: "var(--primary)", display: "inline-block" }} />
                      {p.strong && <strong style={{ color: "var(--ink)", fontWeight: 600 }}>{p.strong}</strong>}{p.rest}
                    </li>
                  ))}
                </ul>
              </div>

              {/* Right block */}
              <div style={{ ...card, padding: "26px 24px" }}>
                <h3 style={{
                  fontFamily: "'Fraunces', serif",
                  fontVariationSettings: '"opsz" 60, "SOFT" 20, "wght" 600',
                  fontSize: 19,
                  color: "var(--ink)",
                  marginBottom: 16,
                  letterSpacing: "-0.01em",
                }}>
                  How it works for a non lawyer
                </h3>
                <ul style={{ listStyle: "none", display: "flex", flexDirection: "column", gap: 10 }}>
                  {B2C_RIGHT.map((p, i) => (
                    <li key={i} style={{ fontSize: 13.5, lineHeight: 1.6, color: "var(--ink-muted)", paddingLeft: 16, position: "relative" }}>
                      <span style={{ position: "absolute", left: 0, top: 8, width: 5, height: 5, borderRadius: "50%", background: "var(--primary)", display: "inline-block" }} />
                      {p.rest}
                    </li>
                  ))}
                </ul>
              </div>
            </div>

          </div>
        </div>

      </div>

      {/* ── Navigation dots ────────────────────────────────────────────── */}
      <div style={{
        position: "fixed",
        bottom: 28,
        left: "50%",
        transform: "translateX(-50%)",
        display: "flex",
        alignItems: "center",
        gap: 14,
        background: "#ffffff",
        border: "1px solid var(--hairline)",
        borderRadius: 999,
        padding: "8px 18px",
        boxShadow: "0 1px 2px rgba(15,23,42,0.04), 0 4px 12px rgba(15,23,42,0.06)",
        zIndex: 50,
      }}>
        <button
          onClick={() => go(-1)}
          disabled={slide === 0}
          style={{ background: "none", border: "none", cursor: slide === 0 ? "default" : "pointer", color: "var(--ink-muted)", fontSize: 20, width: 28, height: 28, display: "flex", alignItems: "center", justifyContent: "center", borderRadius: 6, opacity: slide === 0 ? 0.25 : 1, transition: "opacity 0.2s" }}
          aria-label="Previous"
        >
          ‹
        </button>

        {[0, 1, 2].map(i => (
          <button
            key={i}
            onClick={() => setSlide(i)}
            aria-label={`Slide ${i + 1}`}
            style={{
              width: 7,
              height: 7,
              borderRadius: "50%",
              border: "none",
              background: slide === i ? "var(--primary)" : "var(--hairline)",
              cursor: "pointer",
              padding: 0,
              transform: slide === i ? "scale(1.3)" : "scale(1)",
              transition: "background 0.25s, transform 0.25s",
            }}
          />
        ))}

        <button
          onClick={() => go(1)}
          disabled={slide === TOTAL - 1}
          style={{ background: "none", border: "none", cursor: slide === TOTAL - 1 ? "default" : "pointer", color: "var(--ink-muted)", fontSize: 20, width: 28, height: 28, display: "flex", alignItems: "center", justifyContent: "center", borderRadius: 6, opacity: slide === TOTAL - 1 ? 0.25 : 1, transition: "opacity 0.2s" }}
          aria-label="Next"
        >
          ›
        </button>
      </div>
    </>
  );
}

export default dynamic(() => Promise.resolve(Landing), { ssr: false });

export const getServerSideProps: GetServerSideProps = async () => ({ props: {} });
