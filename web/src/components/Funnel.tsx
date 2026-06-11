import type { Funnel as FunnelData } from "../lib/types";
import { pct } from "../lib/format";

const STAGES: { key: keyof FunnelData; label: string; cls: string }[] = [
  { key: "sent", label: "Sent", cls: "var(--s-sent)" },
  { key: "delivered", label: "Delivered", cls: "var(--s-delivered)" },
  { key: "opened", label: "Opened", cls: "var(--s-opened)" },
  { key: "read", label: "Read", cls: "var(--s-read)" },
  { key: "clicked", label: "Clicked", cls: "var(--s-clicked)" },
];

export function Funnel({ funnel }: { funnel: FunnelData }) {
  const denom = Math.max(funnel.total, 1);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {STAGES.map((s) => {
        const v = funnel[s.key] as number;
        const w = (v / denom) * 100;
        return (
          <div key={s.key}>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "baseline",
                marginBottom: 4,
              }}
            >
              <span className="label">{s.label}</span>
              <span className="mono" style={{ fontSize: 13, fontWeight: 600 }}>
                {v}
              </span>
            </div>
            <div
              style={{
                height: 6,
                background: "var(--panel-2)",
                borderRadius: 999,
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  height: "100%",
                  width: `${w}%`,
                  background: s.cls,
                  borderRadius: 999,
                  transition: "width 0.5s cubic-bezier(.2,.7,.2,1)",
                }}
              />
            </div>
          </div>
        );
      })}

      <hr className="hairline" style={{ margin: "4px 0" }} />

      <div style={{ display: "flex", gap: 18, flexWrap: "wrap" }}>
        <Rate label="Delivery" value={funnel.delivery_rate} />
        <Rate label="Open" value={funnel.open_rate} />
        <Rate label="Click" value={funnel.click_rate} />
        <Rate label="Failed" value={funnel.failure_rate} failed count={funnel.failed} />
      </div>
    </div>
  );
}

function Rate({
  label,
  value,
  failed,
  count,
}: {
  label: string;
  value: number;
  failed?: boolean;
  count?: number;
}) {
  return (
    <div>
      <div className="label" style={{ marginBottom: 2 }}>
        {label}
        {count !== undefined ? `  ·  ${count}` : ""}
      </div>
      <div
        className="mono"
        style={{
          fontSize: 18,
          fontWeight: 600,
          color: failed ? "var(--s-failed)" : "var(--ink)",
        }}
      >
        {pct(value)}
      </div>
    </div>
  );
}
