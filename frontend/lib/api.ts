// Typed client for the FastAPI surface defined in backend/api.py.
//
// Auth: every request carries the Clerk session JWT in
// ``Authorization: Bearer <token>``. Callers obtain the token via
// useAuth().getToken() and pass it in. We deliberately do not stash the
// token in module state so it can be refreshed on every call (Clerk handles
// re-issuing).
//
// SSE: native ``EventSource`` doesn't support custom headers (so no Bearer
// token), and Pages Router static export means we can't use a server-side
// proxy. ``@microsoft/fetch-event-source`` solves both: it speaks SSE over
// fetch with arbitrary headers and POST bodies.

import { fetchEventSource } from "@microsoft/fetch-event-source";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "";

// ── Typed API error ─────────────────────────────────────────────────────
// Carries the HTTP status so callers can branch on 401 vs 429 vs 5xx
// without parsing the message string.

export class ApiError extends Error {
  status: number;
  detail: string;
  constructor(status: number, detail: string) {
    super(`${status} ${detail}`);
    this.status = status;
    this.detail = detail;
    this.name = "ApiError";
  }
}

// ── Types ───────────────────────────────────────────────────────────────

export interface ScoreRow {
  criterion: string;
  plaintiff: number;
  defense: number;
  notes: string;
}

export interface PipelineState {
  plaintiff: string;
  defense: string;
  expert: string;
  judge: string;
  scores: ScoreRow[];
  strategy: string;
  summary: string;
}

export interface ConversationHeader {
  conversation_id: string;
  title: string;
  legal_area: string;
  country: string;
  case_description: string;
  user_position: string;
  created_at: string;
  updated_at: string;
  turn_count: number;
}

export interface ConversationTurn {
  turn_n: number;
  kind: string;
  agents: Record<string, unknown>;
  follow_up_target?: string;
  follow_up_text?: string;
  created_at: string;
}

export interface ConversationDetail {
  header: ConversationHeader;
  turns: ConversationTurn[];
  state: PipelineState | null;
}

export interface MeResponse {
  sub: string;
  email: string;
  name: string;
}

export type RefineTarget =
  | "plaintiff"
  | "defense"
  | "expert"
  | "judge"
  | "strategist";

// ── JSON helpers ────────────────────────────────────────────────────────

async function jsonFetch<T>(
  path: string,
  token: string,
  init?: RequestInit
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      ...(init?.headers ?? {}),
      Authorization: `Bearer ${token}`,
      Accept: "application/json",
    },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    let detail = text;
    try {
      const parsed = JSON.parse(text);
      detail = parsed.detail ?? text;
    } catch {
      // Keep the plain text fallback.
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  me(token: string): Promise<MeResponse> {
    return jsonFetch<MeResponse>("/api/me", token);
  },
  legalAreas(token: string): Promise<{ areas: string[] }> {
    return jsonFetch<{ areas: string[] }>("/api/legal-areas", token);
  },
  listConversations(
    token: string
  ): Promise<{ conversations: ConversationHeader[] }> {
    return jsonFetch<{ conversations: ConversationHeader[] }>(
      "/api/conversations",
      token
    );
  },
  loadConversation(token: string, convId: string): Promise<ConversationDetail> {
    return jsonFetch<ConversationDetail>(
      `/api/conversations/${convId}`,
      token
    );
  },
};

// ── SSE helpers ─────────────────────────────────────────────────────────
// Each pipeline endpoint returns ``update`` events with a partial
// PipelineState, then a single ``done`` event with the conversation id (or
// turn number for follow-ups), or an ``error`` event. The helpers below
// surface these as typed callbacks so React state updates are clean.

interface SSEHandlers {
  onUpdate: (state: PipelineState) => void;
  onDone: (payload: { conversation_id?: string; turn_n?: number }) => void;
  onError: (detail: string) => void;
}

class SSEAbortError extends Error {}

async function postSSE(
  path: string,
  token: string,
  body: unknown,
  handlers: SSEHandlers,
  signal?: AbortSignal
): Promise<void> {
  await fetchEventSource(`${API_BASE}${path}`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify(body),
    signal,
    openWhenHidden: true,

    async onopen(res) {
      if (res.ok) return;
      const text = await res.text().catch(() => res.statusText);
      let detail = text;
      try {
        const parsed = JSON.parse(text);
        detail = parsed.detail ?? text;
      } catch {
        // Keep the plain text fallback.
      }
      throw new ApiError(res.status, detail);
    },

    onmessage(msg) {
      try {
        const data = msg.data ? JSON.parse(msg.data) : {};
        if (msg.event === "update") handlers.onUpdate(data as PipelineState);
        else if (msg.event === "done") handlers.onDone(data);
        else if (msg.event === "error") handlers.onError(data.detail ?? "Unknown error");
      } catch (e) {
        handlers.onError(`Bad SSE payload: ${(e as Error).message}`);
      }
    },

    onerror(err) {
      // Re-throw ApiErrors directly so callers can inspect the status code.
      // For all other errors, wrap in SSEAbortError to prevent auto-retrying.
      if (err instanceof ApiError) throw err;
      throw new SSEAbortError(err instanceof Error ? err.message : String(err));
    },

    onclose() {
      // Server closed the stream cleanly. Already handled via onmessage.
    },
  });
}

export const stream = {
  initial(
    token: string,
    body: {
      case_description: string;
      legal_area: string;
      user_position: string;
      country: string;
    },
    handlers: SSEHandlers,
    signal?: AbortSignal
  ): Promise<void> {
    return postSSE("/api/initial", token, body, handlers, signal);
  },
  finalJudgment(
    token: string,
    conversationId: string,
    handlers: SSEHandlers,
    signal?: AbortSignal
  ): Promise<void> {
    return postSSE(
      "/api/final-judgment",
      token,
      { conversation_id: conversationId },
      handlers,
      signal
    );
  },
  refine(
    token: string,
    body: { conversation_id: string; target: RefineTarget; follow_up_text: string },
    handlers: SSEHandlers,
    signal?: AbortSignal
  ): Promise<void> {
    return postSSE("/api/refine", token, body, handlers, signal);
  },
};
