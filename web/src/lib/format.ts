export function pct(x: number): string {
  return `${(x * 100).toFixed(1)}%`;
}

export function money(x: number): string {
  return `₹${Math.round(x).toLocaleString("en-IN")}`;
}

export function shortId(id: string): string {
  const i = id.indexOf("_");
  return i >= 0 ? id.slice(i + 1) : id;
}

export function relTime(iso: string | null): string {
  if (!iso) return "—";
  const t = new Date(iso).getTime();
  const s = Math.max(0, (Date.now() - t) / 1000);
  if (s < 2) return "now";
  if (s < 60) return `${Math.floor(s)}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  return `${Math.floor(s / 3600)}h ago`;
}

export function clockTime(iso: string | null): string {
  if (!iso) return "--:--:--";
  const d = new Date(iso);
  return d.toLocaleTimeString("en-GB", { hour12: false });
}

const CHANNELS: Record<string, string> = {
  whatsapp: "WhatsApp",
  sms: "SMS",
  email: "Email",
  rcs: "RCS",
};
export function channelLabel(c: string): string {
  return CHANNELS[c] ?? c;
}

const STAGES: Record<string, string> = {
  new: "New",
  active: "Active",
  at_risk: "At risk",
  lapsed: "Lapsed",
  vip: "VIP",
};
export function stageLabel(s: string): string {
  return STAGES[s] ?? s;
}
