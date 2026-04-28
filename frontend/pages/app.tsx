import Head from "next/head";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/router";
import { useAuth, useUser } from "@clerk/nextjs";

import { Sidebar } from "@/components/Sidebar";
import { InputCard } from "@/components/InputCard";
import { AgentPanel, type AgentKey } from "@/components/AgentPanel";
import { MemoCard } from "@/components/MemoCard";
import { ScoresCard } from "@/components/ScoresCard";
import {
  api,
  stream,
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

// localStorage key per Clerk user — so signing in as user B doesn't restore
// user A's last open conversation. Scoped by sub; the sub itself is opaque.
const lastConvKey = (userId: string) => `counselai:lastConv:${userId}`;

export default function CounselAIApp() {
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
      console.warn("listConversations failed", e);
    }
  }, [getToken]);

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
        setError((e as Error).message);
      }
    },
    [getToken]
  );

  const startInitial = useCallback(
    async (payload: CaseHeader) => {
      const t = await getToken();
      if (!t) return;
      cancelInFlight();
      const ctrl = new AbortController();
      abortRef.current = ctrl;
      setBusy(true);
      setError("");
      setState(EMPTY_STATE);
      setActiveId("");
      setCaseHeader(payload);

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
        if (!ctrl.signal.aborted) setError((e as Error).message);
      } finally {
        setBusy(false);
      }
    },
    [getToken, refreshHistory]
  );

  const pronounceJudgment = useCallback(async () => {
    if (!activeId) {
      setError("Run an initial analysis before pronouncing judgment.");
      return;
    }
    const t = await getToken();
    if (!t) return;
    cancelInFlight();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setBusy(true);
    setError("");
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
      if (!ctrl.signal.aborted) setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }, [activeId, getToken, refreshHistory]);

  const refine = useCallback(
    async (target: RefineTarget, follow_up_text: string) => {
      if (!activeId) {
        setError("Run an initial analysis first.");
        return;
      }
      const t = await getToken();
      if (!t) return;
      cancelInFlight();
      const ctrl = new AbortController();
      abortRef.current = ctrl;
      setBusy(true);
      setError("");
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
        if (!ctrl.signal.aborted) setError((e as Error).message);
      } finally {
        setBusy(false);
      }
    },
    [activeId, getToken, refreshHistory]
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
        <title>CounselAI</title>
      </Head>
      <div className="flex min-h-screen">
        <Sidebar
          history={history}
          activeId={activeId}
          onSelect={loadConversation}
          onRefresh={refreshHistory}
          onNewCase={newCase}
        />

        <main className="flex-1 px-10 py-10 max-w-[1400px]">
          <header className="hero mb-9">
            <h1>Legal Counsel Agents</h1>
            <p>
              Five AI legal specialists analyse your case from every angle so
              you walk into proceedings fully prepared. Plaintiff, Defense,
              and Expert run first; pronounce final judgment to bring in the
              Judge and Strategist.
            </p>
          </header>

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
        </main>
      </div>
    </>
  );
}
