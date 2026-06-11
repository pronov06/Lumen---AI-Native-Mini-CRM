import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import type {
  Campaign,
  CampaignStats,
  Communication,
} from "../lib/types";
import type { FeedState } from "../lib/useFeed";
import { Funnel } from "../components/Funnel";
import { StatePill } from "../components/StatePill";
import { channelLabel, relTime } from "../lib/format";

export function Campaigns({
  feed,
  selected,
  onSelect,
}: {
  feed: FeedState;
  selected: string | null;
  onSelect: (id: string | null) => void;
}) {
  const [list, setList] = useState<Campaign[]>([]);
  const [stats, setStats] = useState<CampaignStats | null>(null);
  const [comms, setComms] = useState<Communication[]>([]);

  const loadList = useCallback(async () => {
    try {
      const cs = await api.listCampaigns();
      setList(cs);
      if (!selected && cs.length) onSelect(cs[0].id);
    } catch {
      /* ignore */
    }
  }, [selected, onSelect]);

  useEffect(() => {
    loadList();
  }, [loadList]);

  const refetch = useCallback(async (id: string) => {
    try {
      const [s, c] = await Promise.all([
        api.campaignStats(id),
        api.campaignComms(id),
      ]);
      setStats(s);
      setComms(c);
    } catch {
      /* ignore */
    }
  }, []);

  // Live: refetch the selected campaign as long as events keep landing for it,
  // and poll briefly so the funnel animates toward its settled state.
  const settleRef = useRef(0);
  useEffect(() => {
    if (!selected) {
      setStats(null);
      setComms([]);
      return;
    }
    settleRef.current = 0;
    refetch(selected);
    const iv = window.setInterval(async () => {
      await refetch(selected);
      setStats((s) => {
        if (s && s.funnel.delivered + s.funnel.failed >= s.funnel.total) {
          settleRef.current += 1;
        } else {
          settleRef.current = 0;
        }
        if (settleRef.current > 3) window.clearInterval(iv);
        return s;
      });
    }, 1400);
    return () => window.clearInterval(iv);
  }, [selected, refetch]);

  // Nudge a refetch the instant an event for this campaign hits the feed.
  const lastSeen = useRef(0);
  useEffect(() => {
    if (!selected) return;
    if (feed.total === lastSeen.current) return;
    lastSeen.current = feed.total;
    const hit = feed.events.find((e) => e.campaign_id === selected);
    if (hit) refetch(selected);
  }, [feed.total, feed.events, selected, refetch]);

  return (
    <div style={{ display: "grid", gridTemplateColumns: "230px 1fr", gap: 22 }}>
      {/* list */}
      <div>
        <div className="eyebrow" style={{ marginBottom: 10 }}>
          Campaigns · {list.length}
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {list.length === 0 && (
            <div className="label" style={{ color: "var(--faint)" }}>
              None yet. Compose one to get started.
            </div>
          )}
          {list.map((c) => {
            const active = c.id === selected;
            return (
              <button
                key={c.id}
                onClick={() => onSelect(c.id)}
                className="panel"
                style={{
                  textAlign: "left",
                  padding: "10px 12px",
                  cursor: "pointer",
                  borderColor: active ? "var(--accent)" : "var(--line)",
                  background: active ? "var(--accent-soft)" : "var(--panel)",
                }}
              >
                <div
                  style={{
                    fontSize: 13,
                    fontWeight: 600,
                    marginBottom: 4,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {c.name}
                </div>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                  }}
                >
                  <span className="label">{channelLabel(c.channel)}</span>
                  <span className="mono" style={{ fontSize: 11 }}>
                    {c.recipient_count} rcpt
                  </span>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* detail */}
      <div>
        {!stats ? (
          <div className="label" style={{ color: "var(--faint)" }}>
            Select a campaign.
          </div>
        ) : (
          <div style={{ display: "grid", gap: 18 }}>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 1fr",
                gap: 18,
              }}
            >
              <div className="panel" style={{ padding: 16 }}>
                <div className="eyebrow" style={{ marginBottom: 12 }}>
                  Funnel
                </div>
                <Funnel funnel={stats.funnel} />
              </div>

              <div style={{ display: "grid", gap: 18, alignContent: "start" }}>
                <Metric
                  label="Attributed orders"
                  value={stats.attributed_orders}
                  hint="orders placed after a click"
                  accent
                />
                <Metric
                  label="Recipients"
                  value={stats.recipient_count}
                  hint={`status · ${stats.status}`}
                />
                <Metric
                  label="In flight"
                  value={stats.funnel.queued}
                  hint="still queued"
                />
              </div>
            </div>

            {/* recipients */}
            <div className="panel" style={{ overflow: "hidden" }}>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  padding: "11px 14px",
                  borderBottom: "1px solid var(--line)",
                }}
              >
                <div className="eyebrow">Recipients · {comms.length}</div>
                <div className="label">live</div>
              </div>
              <div style={{ maxHeight: 320, overflowY: "auto" }}>
                {comms.map((c) => (
                  <div
                    key={c.id}
                    style={{
                      display: "grid",
                      gridTemplateColumns: "1fr auto auto",
                      gap: 12,
                      alignItems: "center",
                      padding: "8px 14px",
                      borderBottom: "1px solid var(--line)",
                      fontSize: 12.5,
                    }}
                  >
                    <span
                      className="mono"
                      style={{
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                        color: "var(--muted)",
                      }}
                    >
                      {c.recipient}
                    </span>
                    <span className="label">{relTime(c.updated_at)}</span>
                    <StatePill state={c.state} />
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Metric({
  label,
  value,
  hint,
  accent,
}: {
  label: string;
  value: number;
  hint?: string;
  accent?: boolean;
}) {
  return (
    <div className="panel" style={{ padding: 16 }}>
      <div className="label" style={{ marginBottom: 6 }}>
        {label}
      </div>
      <div
        className="mono"
        style={{
          fontSize: 30,
          fontWeight: 600,
          lineHeight: 1,
          color: accent ? "var(--accent-ink)" : "var(--ink)",
        }}
      >
        {value}
      </div>
      {hint && (
        <div className="label" style={{ marginTop: 6, color: "var(--faint)" }}>
          {hint}
        </div>
      )}
    </div>
  );
}
