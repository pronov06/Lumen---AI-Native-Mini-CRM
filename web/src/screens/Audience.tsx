import type { CustomerStats } from "../lib/types";
import { channelLabel, stageLabel } from "../lib/format";

const STAGE_ORDER = ["vip", "active", "new", "at_risk", "lapsed"];
const STAGE_COLOR: Record<string, string> = {
  vip: "var(--s-clicked)",
  active: "var(--s-read)",
  new: "var(--s-delivered)",
  at_risk: "var(--s-opened)",
  lapsed: "var(--s-sent)",
};

export function Audience({ stats }: { stats: CustomerStats | null }) {
  if (!stats) {
    return (
      <div className="label" style={{ color: "var(--faint)" }}>
        Loading audience…
      </div>
    );
  }
  const total = Math.max(stats.total, 1);
  const stages = STAGE_ORDER.filter((s) => s in stats.by_stage);

  return (
    <div style={{ maxWidth: 720 }}>
      <div className="eyebrow">Audience</div>
      <h1
        style={{
          fontSize: 24,
          fontWeight: 700,
          letterSpacing: "-0.02em",
          margin: "6px 0 18px",
        }}
      >
        {stats.total.toLocaleString("en-IN")} customers, by lifecycle
      </h1>

      <div className="panel" style={{ padding: 18, marginBottom: 18 }}>
        <div className="eyebrow" style={{ marginBottom: 14 }}>
          Lifecycle stage
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {stages.map((s) => {
            const v = stats.by_stage[s];
            return (
              <div key={s}>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    marginBottom: 4,
                  }}
                >
                  <span style={{ fontSize: 13 }}>{stageLabel(s)}</span>
                  <span className="mono" style={{ fontWeight: 600 }}>
                    {v}
                  </span>
                </div>
                <div
                  style={{
                    height: 8,
                    background: "var(--panel-2)",
                    borderRadius: 999,
                    overflow: "hidden",
                  }}
                >
                  <div
                    style={{
                      height: "100%",
                      width: `${(v / total) * 100}%`,
                      background: STAGE_COLOR[s],
                      borderRadius: 999,
                    }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="panel" style={{ padding: 18 }}>
        <div className="eyebrow" style={{ marginBottom: 14 }}>
          Channel opt-in
        </div>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(4, 1fr)",
            gap: 14,
          }}
        >
          {Object.entries(stats.by_channel).map(([c, v]) => (
            <div key={c}>
              <div className="label" style={{ marginBottom: 4 }}>
                {channelLabel(c)}
              </div>
              <div className="mono" style={{ fontSize: 24, fontWeight: 600 }}>
                {v}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
