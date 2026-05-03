import Head from "next/head";
import dynamic from "next/dynamic";
import type { GetServerSideProps } from "next";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/router";
import { useAuth, useUser } from "@clerk/nextjs";

import { Sidebar } from "@/components/Sidebar";
import { InputCard } from "@/components/InputCard";
import { AgentPanel, type AgentKey } from "@/components/AgentPanel";
import { MemoCard } from "@/components/MemoCard";
import { ScoresCard } from "@/components/ScoresCard";
import { UserMenu } from "@/components/UserMenu";
import {
  api,
  stream,
  ApiError,
  type ConversationHeader,
  type PipelineState,
  type RefineTarget,
} from "@/lib/api";
import {
  DEFAULT_COUNTRY,
  EMPTY_STATE,
  JUDGE_PLACEHOLDER,
  STRATEGY_PLACEHOLDER,
} from "@/lib/constants";

type CaseHeader = { case: string; area: string; position: string; country: string };

// 3 minutes — enough for the longest cascade (5 agents), with headroom.
const STREAM_TIMEOUT_MS = 180_000;

// Translate an API error into a user-facing string.
// 401 → caller should redirect; 429 → backend message is already friendly;
// everything else → generic message that doesn't leak internals.
function apiErrorMessage(e: unknown): { msg: string; isAuth: boolean } {
  if (e instanceof ApiError) {
    if (e.status === 401) return { msg: "", isAuth: true };
    if (e.status === 429) return { msg: e.detail, isAuth: false };
    if (e.status === 404) return { msg: "Conversation not found.", isAuth: false };
    return { msg: "Something went wrong. Please try again.", isAuth: false };
  }
  return { msg: (e as Error).message ?? "Something went wrong.", isAuth: false };
}

// localStorage key per Clerk user — so signing in as user B doesn't restore
// user A's last open conversation. Scoped by sub; the sub itself is opaque.
const lastConvKey = (userId: string) => `counselai:lastConv:${userId}`;

function MoootCourtApp() {
  const router = useRouter();
  const { getToken, isLoaded, isSignedIn } = useAuth();
  const { user } = useUser();

  const [history, setHistory] = useState<ConversationHeader[]>([]);
  const [activeId, setActiveId] = useState<string>("");
  const [state, setState] = useState<PipelineState>(EMPTY_STATE);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>("");
  const [caseHeader, setCaseHeader] = useState<CaseHeader>({
    case: "",
    area: "Contract Law",
    position: "",
    country: DEFAULT_COUNTRY,
  });
  // Tracks whether we've already attempted the first restore for this signed-in
  // user. Prevents the restore from clobbering state every time history refreshes.
  const restoredRef = useRef(false);

  const abortRef = useRef<AbortController | null>(null);

  // Redirect unauthenticated users to /.
  useEffect(() => {
    if (isLoaded && !isSignedIn) router.replace("/");
  }, [isLoaded, isSignedIn, router]);

  const refreshHistory = useCallback(async () => {
    try {
      const t = await getToken();
      if (!t) return;
      const { conversations } = await api.listConversations(t);
      setHistory(conversations);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        router.replace("/");
        return;
      }
      setError("Failed to load conversation history. Refresh the page to try again.");
    }
  }, [getToken, router]);

  useEffect(() => {
    if (isLoaded && isSignedIn) refreshHistory();
  }, [isLoaded, isSignedIn, refreshHistory]);

  // Persist activeId locally so a hard reload restores the user's last
  // open conversation. Server-side state is already authoritative; this
  // is just a pointer.
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!user?.id) return;
    if (activeId) {
      window.localStorage.setItem(lastConvKey(user.id), activeId);
    }
  }, [activeId, user?.id]);

  // After history resolves, restore the saved conversation once per session.
  // We confirm the saved id is still in the user's history before loading
  // (handles the case where a conversation was deleted server-side).
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!user?.id) return;
    if (restoredRef.current) return;
    if (history.length === 0) return;

    const saved = window.localStorage.getItem(lastConvKey(user.id));
    if (saved && history.some((c) => c.conversation_id === saved)) {
      restoredRef.current = true;
      void loadConversation(saved);
    } else {
      restoredRef.current = true;
    }
    // loadConversation is stable across renders (memoised below).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [history, user?.id]);

  const cancelInFlight = () => {
    abortRef.current?.abort();
    abortRef.current = null;
  };

  const loadConversation = useCallback(
    async (convId: string) => {
      try {
        const t = await getToken();
        if (!t) return;
        const detail = await api.loadConversation(t, convId);
        setActiveId(convId);
        setState(detail.state ?? EMPTY_STATE);
        setCaseHeader({
          case: detail.header.case_description ?? "",
          area: detail.header.legal_area ?? "Contract Law",
          position: detail.header.user_position ?? "",
          country: detail.header.country || DEFAULT_COUNTRY,
        });
        setError("");
      } catch (e) {
        const { msg, isAuth } = apiErrorMessage(e);
        if (isAuth) { router.replace("/"); return; }
        setError(msg);
      }
    },
    [getToken, router]
  );

  const startInitial = useCallback(
    async (payload: CaseHeader) => {
      const t = await getToken();
      if (!t) { setError("Session expired. Please sign in again."); return; }
      cancelInFlight();
      const ctrl = new AbortController();
      abortRef.current = ctrl;
      setBusy(true);
      setError("");
      setState(EMPTY_STATE);
      setActiveId("");
      setCaseHeader(payload);

      let timedOut = false;
      const timeoutId = setTimeout(() => { timedOut = true; ctrl.abort(); }, STREAM_TIMEOUT_MS);
      try {
        await stream.initial(
          t,
          {
            case_description: payload.case,
            legal_area: payload.area,
            user_position: payload.position,
            country: payload.country,
          },
          {
            onUpdate: (s) => setState(s),
            onDone: ({ conversation_id }) => {
              if (conversation_id) setActiveId(conversation_id);
              refreshHistory();
            },
            onError: (detail) => setError(detail),
          },
          ctrl.signal
        );
      } catch (e) {
        if (ctrl.signal.aborted) {
          if (timedOut) setError("The analysis timed out. Please try again.");
        } else {
          const { msg, isAuth } = apiErrorMessage(e);
          if (isAuth) { router.replace("/"); return; }
          setError(msg);
        }
      } finally {
        clearTimeout(timeoutId);
        setBusy(false);
      }
    },
    [getToken, refreshHistory, router]
  );

  const pronounceJudgment = useCallback(async () => {
    if (!activeId) {
      setError("Run an initial analysis before pronouncing judgment.");
      return;
    }
    const t = await getToken();
    if (!t) { setError("Session expired. Please sign in again."); return; }
    cancelInFlight();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setBusy(true);
    setError("");

    let timedOut = false;
    const timeoutId = setTimeout(() => { timedOut = true; ctrl.abort(); }, STREAM_TIMEOUT_MS);
    try {
      await stream.finalJudgment(
        t,
        activeId,
        {
          onUpdate: (s) => setState(s),
          onDone: () => refreshHistory(),
          onError: (detail) => setError(detail),
        },
        ctrl.signal
      );
    } catch (e) {
      if (ctrl.signal.aborted) {
        if (timedOut) setError("The analysis timed out. Please try again.");
      } else {
        const { msg, isAuth } = apiErrorMessage(e);
        if (isAuth) { router.replace("/"); return; }
        setError(msg);
      }
    } finally {
      clearTimeout(timeoutId);
      setBusy(false);
    }
  }, [activeId, getToken, refreshHistory, router]);

  const refine = useCallback(
    async (target: RefineTarget, follow_up_text: string) => {
      if (!activeId) {
        setError("Run an initial analysis first.");
        return;
      }
      const t = await getToken();
      if (!t) { setError("Session expired. Please sign in again."); return; }
      cancelInFlight();
      const ctrl = new AbortController();
      abortRef.current = ctrl;
      setBusy(true);
      setError("");

      let timedOut = false;
      const timeoutId = setTimeout(() => { timedOut = true; ctrl.abort(); }, STREAM_TIMEOUT_MS);
      try {
        await stream.refine(
          t,
          { conversation_id: activeId, target, follow_up_text },
          {
            onUpdate: (s) => setState(s),
            onDone: () => refreshHistory(),
            onError: (detail) => setError(detail),
          },
          ctrl.signal
        );
      } catch (e) {
        if (ctrl.signal.aborted) {
          if (timedOut) setError("The analysis timed out. Please try again.");
        } else {
          const { msg, isAuth } = apiErrorMessage(e);
          if (isAuth) { router.replace("/"); return; }
          setError(msg);
        }
      } finally {
        clearTimeout(timeoutId);
        setBusy(false);
      }
    },
    [activeId, getToken, refreshHistory, router]
  );

  const newCase = () => {
    cancelInFlight();
    setBusy(false);
    setActiveId("");
    setState(EMPTY_STATE);
    setCaseHeader({
      case: "",
      area: "Contract Law",
      position: "",
      country: DEFAULT_COUNTRY,
    });
    setError("");
    // Forget the saved active conversation so a reload starts fresh too.
    if (typeof window !== "undefined" && user?.id) {
      window.localStorage.removeItem(lastConvKey(user.id));
    }
  };

  // Phase 2 has run iff judge content is non-placeholder text. Used to gate
  // the Pronounce button label and which agents accept refines.
  const judgmentRendered = useMemo(
    () => Boolean(state.judge) && state.judge !== JUDGE_PLACEHOLDER,
    [state.judge]
  );

  return (
    <>
      <Head>
        <title>MoootCourt</title>
      </Head>
      <div className="app-shell">
        <Sidebar
          history={history}
          activeId={activeId}
          onSelect={loadConversation}
          onRefresh={refreshHistory}
          onNewCase={newCase}
        />

        <main className="app-main">
          <div className="app-canvas">
            <div className="flex justify-end mb-6">
              <UserMenu />
            </div>

            <InputCard
              busy={busy}
              initial={caseHeader}
              onAnalyse={({ case: c, area, position, country }) =>
                startInitial({ case: c, area, position, country })
              }
            />

            {error && (
              <div className="mb-6 px-4 py-3 border border-rose-500 bg-rose-500/5 text-rose-600 rounded-sm text-sm">
                {error}
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <AgentPanel
                agent="plaintiff"
                title="Plaintiff's Counsel"
                body={state.plaintiff}
                placeholder="Argument will appear here after analysis."
                busy={busy}
                onRefine={(t) => refine("plaintiff", t)}
              />
              <AgentPanel
                agent="defense"
                title="Defense Counsel"
                body={state.defense}
                placeholder="Counter-argument will appear here after analysis."
                busy={busy}
                onRefine={(t) => refine("defense", t)}
              />
              <AgentPanel
                agent="expert"
                title="Expert Witness"
                body={state.expert}
                placeholder="Expert technical analysis will appear here."
                busy={busy}
                onRefine={(t) => refine("expert", t)}
              />
              <AgentPanel
                agent="judge"
                title="Judge's Assessment"
                body={state.judge}
                placeholder={JUDGE_PLACEHOLDER}
                refinable={judgmentRendered}
                busy={busy}
                onRefine={(t) => refine("judge", t)}
              />
            </div>

            <div className="flex justify-center my-10">
              <button
                type="button"
                className="final-judgment-btn"
                onClick={pronounceJudgment}
                disabled={busy || !activeId}
              >
                {judgmentRendered ? "Re-run Final Judgment" : "Pronounce Final Judgment"}
              </button>
            </div>

            <MemoCard
              body={state.strategy || STRATEGY_PLACEHOLDER}
              busy={busy}
              refinable={judgmentRendered}
              onRefine={(t) => refine("strategist", t)}
            />

            <ScoresCard rows={state.scores} />

            <p className="disclaimer">
              This tool provides AI-generated legal simulations and is not a
              substitute for professional legal advice. The scores and
              assessments are based on the input provided. Always consult with a
              licensed attorney for final legal decisions.
            </p>

            <p className="text-center text-xs text-slate-400 font-mono tracking-[0.05em] mt-6 mb-6">
              2026 · Malambo Mutila
            </p>
          </div>
        </main>
      </div>
    </>
  );
}

export default dynamic(() => Promise.resolve(MoootCourtApp), { ssr: false });

export const getServerSideProps: GetServerSideProps = async () => ({
  props: {},
});
