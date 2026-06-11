import { useState } from "react";
import { api } from "../lib/api";
import type { Campaign, Proposal } from "../lib/types";
import { channelLabel, stageLabel } from "../lib/format";

const CHANNELS = ["whatsapp", "sms", "email", "rcs"];

const SUGGESTIONS = [
  "Win back lapsed customers with a one-time 20% offer",
  "Reward VIPs with early access to the new single-origin roast",
  "Nudge at-risk regulars in Mumbai before they churn",
];

export function Compose({
  onApproved,
  onChanged,
}: {
  onApproved: (id: string) => void;
  onChanged: () => void;
}) {
  const [goal, setGoal] = useState("");
  const [proposing, setProposing] = useState(false);
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [channel, setChannel] = useState("whatsapp");
  const [message, setMessage] = useState("");
  const [draft, setDraft] = useState<Campaign | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const propose = async (g: string) => {
    setError(null);
    setProposing(true);
    setDraft(null);
    try {
      const p = await api.propose(g);
      setProposal(p);
      setChannel(p.channel);
      setMessage(p.message);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setProposing(false);
    }
  };

  const createDraft = async () => {
    if (!proposal) return;
    setError(null);
    setBusy(true);
    try {
      const c = await api.createCampaign({
        name: proposal.goal.slice(0, 80),
        segment: proposal.segment,
        channel,
        message,
      });
      setDraft(c);
      onChanged();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const approve = async () => {
    if (!draft) return;
    setError(null);
    setBusy(true);
    try {
      await api.approve(draft.id);
      onApproved(draft.id);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  };

  return (
    <div style={{ maxWidth: 760 }}>
      <div className="eyebrow">Campaign co-pilot</div>
      <h1
        style={{
          fontSize: 24,
          fontWeight: 700,
          letterSpacing: "-0.02em",
          margin: "6px 0 4px",
        }}
      >
        Describe who to reach. Approve before anything sends.
      </h1>
      <p style={{ color: "var(--muted)", marginBottom: 18 }}>
        State a goal in plain language. The co-pilot proposes a segment, channel,
        and message — you review and edit, then you are the one who launches it.
      </p>

      {/* goal input */}
      <div style={{ display: "flex", gap: 8 }}>
        <input
          className="field"
          placeholder="e.g. Win back lapsed customers with a 20% offer"
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && goal.trim().length > 2) propose(goal);
          }}
        />
        <button
          className="btn btn-primary"
          disabled={proposing || goal.trim().length < 3}
          onClick={() => propose(goal)}
          style={{ whiteSpace: "nowrap" }}
        >
          {proposing ? "Drafting…" : "Draft campaign"}
        </button>
      </div>

      {!proposal && (
        <div style={{ marginTop: 12, display: "flex", gap: 8, flexWrap: "wrap" }}>
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              className="btn"
              style={{ fontSize: 11.5, fontWeight: 400 }}
              onClick={() => {
                setGoal(s);
                propose(s);
              }}
            >
              {s}
            </button>
          ))}
        </div>
      )}

      {error && (
        <div
          className="panel"
          style={{
            marginTop: 16,
            padding: "11px 14px",
            borderColor: "var(--s-failed)",
            color: "var(--s-failed)",
            fontSize: 13,
          }}
        >
          {error}
        </div>
      )}

      {proposal && (
        <div className="panel" style={{ marginTop: 18, overflow: "hidden" }}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              padding: "12px 16px",
              borderBottom: "1px solid var(--line)",
            }}
          >
            <div className="eyebrow">Proposed plan</div>
            <span
              className="label"
              title="Where this plan came from"
              style={{
                padding: "2px 8px",
                borderRadius: 999,
                background: "var(--panel-2)",
              }}
            >
              {proposal.source === "gemini"
                ? "Gemini"
                : proposal.source === "openrouter"
                ? "OpenRouter"
                : "Local planner"}
            </span>
          </div>

          <div style={{ padding: 16, display: "grid", gap: 16 }}>
            {/* audience */}
            <div>
              <div className="label" style={{ marginBottom: 6 }}>
                Audience
              </div>
              <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
                <span
                  className="mono"
                  style={{ fontSize: 30, fontWeight: 600, lineHeight: 1 }}
                >
                  {proposal.preview.count}
                </span>
                <span className="label">
                  of {proposal.preview.total} customers ·{" "}
                  {proposal.segment_human}
                </span>
              </div>
              {proposal.preview.sample.length > 0 && (
                <div
                  style={{
                    marginTop: 10,
                    display: "flex",
                    flexWrap: "wrap",
                    gap: 6,
                  }}
                >
                  {proposal.preview.sample.slice(0, 6).map((s) => (
                    <span
                      key={s.email}
                      className="mono"
                      style={{
                        fontSize: 11,
                        padding: "3px 8px",
                        background: "var(--panel-2)",
                        borderRadius: 999,
                        color: "var(--muted)",
                      }}
                    >
                      {s.name} · {stageLabel(s.lifecycle_stage)}
                    </span>
                  ))}
                </div>
              )}
            </div>

            {/* reasoning */}
            {proposal.reasoning && (
              <div
                style={{
                  fontSize: 13,
                  color: "var(--muted)",
                  borderLeft: "2px solid var(--line-strong)",
                  paddingLeft: 12,
                }}
              >
                {proposal.reasoning}
              </div>
            )}

            {proposal.warnings?.length > 0 && (
              <div style={{ fontSize: 12.5, color: "var(--s-read)" }}>
                {proposal.warnings.map((w, i) => (
                  <div key={i}>⚠ {w}</div>
                ))}
              </div>
            )}

            {/* channel */}
            <div>
              <div className="label" style={{ marginBottom: 6 }}>
                Channel
              </div>
              <div style={{ display: "flex", gap: 6 }}>
                {CHANNELS.map((c) => (
                  <button
                    key={c}
                    className="btn"
                    onClick={() => setChannel(c)}
                    style={{
                      fontSize: 12,
                      background:
                        channel === c ? "var(--accent-soft)" : undefined,
                      borderColor:
                        channel === c ? "var(--accent)" : undefined,
                      color: channel === c ? "var(--accent-ink)" : undefined,
                      fontWeight: channel === c ? 600 : 500,
                    }}
                  >
                    {channelLabel(c)}
                  </button>
                ))}
              </div>
            </div>

            {/* message */}
            <div>
              <div
                className="label"
                style={{
                  marginBottom: 6,
                  display: "flex",
                  justifyContent: "space-between",
                }}
              >
                <span>Message</span>
                <span className="mono" style={{ color: "var(--faint)" }}>
                  {message.length}
                </span>
              </div>
              <textarea
                className="field mono"
                style={{ fontSize: 13 }}
                value={message}
                onChange={(e) => setMessage(e.target.value)}
              />
            </div>

            <hr className="hairline" />

            {/* HITL gate */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: 12,
              }}
            >
              <div className="label">
                {draft
                  ? "Draft saved. Nothing has sent yet — you hold the gate."
                  : "Step 1 — save as draft. Step 2 — you approve to launch."}
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                <button
                  className="btn"
                  onClick={createDraft}
                  disabled={busy || message.trim().length === 0}
                >
                  {draft ? "Draft saved" : busy ? "Saving…" : "Create draft"}
                </button>
                <button
                  className="btn btn-primary"
                  onClick={approve}
                  disabled={!draft || busy}
                  title={
                    draft
                      ? "Launch this campaign"
                      : "Create a draft first"
                  }
                >
                  {busy && draft ? "Launching…" : "Approve & launch"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
