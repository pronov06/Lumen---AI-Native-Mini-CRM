import { StatePill } from "./StatePill";
import { channelLabel, clockTime, shortId } from "../lib/format";
import type { FeedState } from "../lib/useFeed";

export function LiveFeed({ feed }: { feed: FeedState }) {
  return (
    <div
      className="panel"
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "12px 14px",
          borderBottom: "1px solid var(--line)",
        }}
      >
        <div className="eyebrow">Delivery feed</div>
        {feed.connected ? (
          <span className="live">
            <span className="beacon" />
            live
          </span>
        ) : (
          <span className="label" style={{ color: "var(--s-failed)" }}>
            reconnecting…
          </span>
        )}
      </div>

      <div style={{ flex: 1, overflowY: "auto", overflowX: "hidden" }}>
        {feed.events.length === 0 ? (
          <div
            className="label"
            style={{ padding: "18px 14px", color: "var(--faint)" }}
          >
            No events yet. Approve a campaign and receipts stream in here as the
            channel delivers, opens, and clicks land — in real time, out of order,
            and deduplicated.
          </div>
        ) : (
          feed.events.map((e) => (
            <div
              key={`${e.communication_id}-${e.at}`}
              className="flash"
              style={{
                display: "grid",
                gridTemplateColumns: "auto auto 1fr auto",
                gap: 10,
                alignItems: "center",
                padding: "7px 14px",
                borderBottom: "1px solid var(--line)",
                fontSize: 12,
              }}
            >
              <span className="mono" style={{ color: "var(--faint)" }}>
                {clockTime(e.at)}
              </span>
              <span className="mono" style={{ color: "var(--muted)" }}>
                {shortId(e.communication_id).slice(0, 8)}
              </span>
              <span className="label">{channelLabel(e.channel)}</span>
              <StatePill state={e.state} />
            </div>
          ))
        )}
      </div>

      <div
        style={{
          padding: "9px 14px",
          borderTop: "1px solid var(--line)",
          display: "flex",
          justifyContent: "space-between",
        }}
      >
        <span className="label">Events received</span>
        <span className="mono" style={{ fontWeight: 600 }}>
          {feed.total}
        </span>
      </div>
    </div>
  );
}
