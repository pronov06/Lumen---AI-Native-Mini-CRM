import type {
  Campaign,
  CampaignStats,
  Communication,
  CustomerStats,
  DeadLetter,
  Proposal,
  SegmentPreview,
} from "./types";

const API_BASE: string =
  (import.meta.env.VITE_API_BASE as string) ||
  (window.location.port === "5173" ? "http://localhost:8000" : "");

const isSecure = window.location.protocol === "https:";
const defaultWs = window.location.port === "5173"
  ? "ws://localhost:8000"
  : `${isSecure ? "wss" : "ws"}://${window.location.host}`;

export const WS_BASE: string =
  (import.meta.env.VITE_WS_BASE as string) || defaultWs;

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "content-type": "application/json", ...(init?.headers || {}) },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? JSON.stringify(body);
    } catch {
      /* keep statusText */
    }
    throw new Error(`${res.status} · ${detail}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  seed: (n_customers = 240, seed = 7) =>
    req<{ status: string; customers: number; orders: number; brand: string }>(
      "/seed",
      { method: "POST", body: JSON.stringify({ n_customers, seed }) },
    ),

  customerStats: () => req<CustomerStats>("/customers/stats"),

  propose: (goal: string) =>
    req<Proposal>("/copilot/propose", {
      method: "POST",
      body: JSON.stringify({ goal }),
    }),

  preview: (segment: Record<string, unknown>) =>
    req<SegmentPreview>("/segments/preview", {
      method: "POST",
      body: JSON.stringify({ segment }),
    }),

  createCampaign: (body: {
    name: string;
    segment: Record<string, unknown>;
    channel: string;
    message: string;
  }) =>
    req<Campaign>("/campaigns", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  listCampaigns: () =>
    req<{ campaigns: Campaign[] }>("/campaigns").then((r) => r.campaigns),

  approve: (id: string) =>
    req<{ campaign_id: string; status: string; dispatched: number }>(
      `/campaigns/${id}/approve`,
      { method: "POST" },
    ),

  campaignStats: (id: string) =>
    req<CampaignStats>(`/campaigns/${id}/stats`),

  campaignComms: (id: string) =>
    req<{ communications: Communication[] }>(
      `/campaigns/${id}/communications`,
    ).then((r) => r.communications),

  deadLetters: () =>
    req<{ dead_letters: DeadLetter[] }>("/dead-letters").then(
      (r) => r.dead_letters,
    ),
};
