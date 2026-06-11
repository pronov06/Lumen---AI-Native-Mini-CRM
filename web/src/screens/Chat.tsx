import { useState, useRef, useEffect } from "react";
import { api } from "../lib/api";
import type { Campaign, Proposal } from "../lib/types";
import { channelLabel, stageLabel } from "../lib/format";


const SUGGESTIONS = [
  "Win back lapsed customers with a one-time 20% offer",
  "Reward VIPs with early access to the new single-origin roast",
  "Nudge at-risk regulars in Mumbai before they churn",
];

type Message = {
  id: string;
  sender: "user" | "assistant" | "agent";
  text: string;
  proposal?: Proposal;
  isExecuting?: boolean;
  agentLogs?: string[];
  finishedCampaign?: Campaign;
};

export function Chat({
  onApproved,
  onChanged,
}: {
  onApproved: (id: string) => void;
  onChanged: () => void;
}) {
  const [goal, setGoal] = useState("");
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      sender: "assistant",
      text: "Hello! I am your AI Campaign Assistant. Describe your campaign goal, and I'll recommend the segment, channel, and message. I can also execute the campaign end-to-end autonomously.",
    },
  ]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const sendGoal = async (text: string) => {
    if (!text.trim()) return;
    setError(null);
    setLoading(true);

    const userMsg: Message = {
      id: `u-${Date.now()}`,
      sender: "user",
      text: text,
    };
    setMessages((prev) => [...prev, userMsg]);
    setGoal("");

    try {
      const p = await api.propose(text);
      const assistantMsg: Message = {
        id: `a-${Date.now()}`,
        sender: "assistant",
        text: `Here is the proposed plan for: "${text}"`,
        proposal: p,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (e) {
      setError((e as Error).message);
      const errorMsg: Message = {
        id: `err-${Date.now()}`,
        sender: "assistant",
        text: `Error drafting plan: ${(e as Error).message}`,
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  const refinePlan = async (originalGoal: string, instruction: string) => {
    const query = `refine message: "${instruction}". Original goal: ${originalGoal}`;
    sendGoal(query);
  };

  const executeCampaignAutonomously = async (proposal: Proposal) => {
    const agentMsgId = `agent-${Date.now()}`;
    const initialLogs = ["🔍 Analyzing campaign goal and target segment..."];
    
    const newAgentMsg: Message = {
      id: agentMsgId,
      sender: "agent",
      text: `Autonomous Campaign Execution Started for: "${proposal.goal}"`,
      isExecuting: true,
      agentLogs: initialLogs,
    };

    setMessages((prev) => [...prev, newAgentMsg]);

    const updateLogs = (log: string) => {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === agentMsgId
            ? { ...m, agentLogs: [...(m.agentLogs || []), log] }
            : m
        )
      );
    };

    try {
      // Step 1: Evaluating segment count
      await new Promise((r) => setTimeout(r, 1500));
      updateLogs(`📊 Calculating target audience size... Found ${proposal.preview.count} shoppers matching criteria.`);

      // Step 2: Creating draft
      await new Promise((r) => setTimeout(r, 1500));
      updateLogs("💾 Registering draft campaign in CRM...");
      const draft = await api.createCampaign({
        name: proposal.goal.slice(0, 80),
        segment: proposal.segment,
        channel: proposal.channel,
        message: proposal.message,
      });
      updateLogs(`✓ Draft campaign created with ID: ${draft.id}`);
      onChanged();

      // Step 3: Approving and launching campaign
      await new Promise((r) => setTimeout(r, 1500));
      updateLogs("🚀 Approving campaign and starting delivery...");
      await api.approve(draft.id);
      updateLogs("🟢 Campaign approved and launched successfully! Sending messages live...");

      // Finalize
      await new Promise((r) => setTimeout(r, 500));
      setMessages((prev) =>
        prev.map((m) =>
          m.id === agentMsgId
            ? {
                ...m,
                isExecuting: false,
                finishedCampaign: draft,
              }
            : m
        )
      );
    } catch (e) {
      updateLogs(`❌ Agent failed execution: ${(e as Error).message}`);
      setMessages((prev) =>
        prev.map((m) =>
          m.id === agentMsgId
            ? { ...m, isExecuting: false }
            : m
        )
      );
    }
  };

  const createDraftOnly = async (proposal: Proposal) => {
    try {
      const c = await api.createCampaign({
        name: proposal.goal.slice(0, 80),
        segment: proposal.segment,
        channel: proposal.channel,
        message: proposal.message,
      });
      onChanged();
      setMessages((prev) => [
        ...prev,
        {
          id: `draft-${Date.now()}`,
          sender: "assistant",
          text: `✓ Campaign draft created with ID ${c.id}. You can review and launch it under the Campaigns tab.`,
        },
      ]);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <div style={{ maxWidth: 760, height: "calc(100vh - 100px)", display: "flex", flexDirection: "column" }}>
      <div className="eyebrow" style={{ marginBottom: 6 }}>AI Chat Assistant & Agent</div>
      <h1 style={{ fontSize: 22, fontWeight: 700, letterSpacing: "-0.02em", margin: "0 0 12px" }}>
        Lumen Conversational Console
      </h1>

      {/* Messages Feed */}
      <div style={{ flex: 1, overflowY: "auto", padding: "10px 0", display: "flex", flexDirection: "column", gap: 16 }}>
        {messages.map((m) => (
          <div
            key={m.id}
            style={{
              alignSelf: m.sender === "user" ? "flex-end" : "flex-start",
              maxWidth: m.proposal || m.agentLogs ? "100%" : "80%",
              width: m.proposal || m.agentLogs ? "100%" : "auto",
              display: "flex",
              flexDirection: "column",
              alignItems: m.sender === "user" ? "flex-end" : "flex-start",
            }}
          >
            {/* Sender Label */}
            <span className="eyebrow" style={{ fontSize: 9, marginBottom: 4, display: "block" }}>
              {m.sender === "user" ? "Marketer" : m.sender === "agent" ? "Lumen Agent" : "Lumen Assistant"}
            </span>

            {/* Bubble */}
            <div
              className="panel"
              style={{
                padding: "12px 16px",
                background: m.sender === "user" ? "var(--panel-2)" : "var(--panel)",
                borderRadius: "var(--r)",
                border: m.sender === "user" ? "1px solid var(--line-strong)" : "1px solid var(--line)",
                width: m.proposal || m.agentLogs ? "100%" : "auto",
              }}
            >
              <div style={{ fontSize: 13.5, whiteSpace: "pre-wrap" }}>{m.text}</div>

              {/* Proposed Plan Render Card */}
              {m.proposal && (
                <div className="panel" style={{ marginTop: 12, border: "1px solid var(--line-strong)", background: "var(--paper)" }}>
                  <div style={{ padding: "10px 14px", borderBottom: "1px solid var(--line)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <span className="eyebrow" style={{ fontSize: 9.5 }}>Proposed Campaign Plan</span>
                    <span className="label" style={{ fontSize: 9 }}>Source: {m.proposal.source}</span>
                  </div>

                  <div style={{ padding: 14, display: "grid", gap: 12 }}>
                    {/* Audience Segment */}
                    <div>
                      <div className="label" style={{ marginBottom: 4 }}>Audience</div>
                      <div style={{ fontSize: 14, fontWeight: 600 }}>
                        {m.proposal.preview.count} <span style={{ fontWeight: 400, color: "var(--muted)" }}>of {m.proposal.preview.total} customers · {m.proposal.segment_human}</span>
                      </div>
                      {m.proposal.preview.sample.length > 0 && (
                        <div style={{ marginTop: 8, display: "flex", flexWrap: "wrap", gap: 4 }}>
                          {m.proposal.preview.sample.slice(0, 4).map((s) => (
                            <span key={s.email} className="mono" style={{ fontSize: 10, padding: "2px 6px", background: "var(--panel-2)", borderRadius: 999, color: "var(--muted)" }}>
                              {s.name} · {stageLabel(s.lifecycle_stage)}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>

                    {/* Recommendation and Warnings */}
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                      <div>
                        <div className="label" style={{ marginBottom: 2 }}>Channel</div>
                        <div style={{ fontWeight: 600, fontSize: 13, textTransform: "capitalize" }}>
                          {channelLabel(m.proposal.channel)}
                        </div>
                      </div>
                      <div>
                        <div className="label" style={{ marginBottom: 2 }}>Reasoning</div>
                        <div style={{ fontSize: 12, color: "var(--muted)", fontStyle: "italic" }}>
                          {m.proposal.reasoning}
                        </div>
                      </div>
                    </div>

                    {/* Message Text */}
                    <div>
                      <div className="label" style={{ marginBottom: 4 }}>Message Content</div>
                      <div className="mono" style={{ background: "var(--panel)", padding: "10px 12px", border: "1px solid var(--line)", borderRadius: "var(--r)", fontSize: 12.5, whiteSpace: "pre-wrap" }}>
                        {m.proposal.message}
                      </div>
                    </div>

                    <hr className="hairline" />

                    {/* Actions and Refinement */}
                    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                        <button
                          className="btn"
                          style={{ fontSize: 11.5 }}
                          onClick={() => refinePlan(m.proposal!.goal, "Make it sound more premium")}
                        >
                          ✦ Refine: Make Tone Premium
                        </button>
                        <button
                          className="btn"
                          style={{ fontSize: 11.5 }}
                          onClick={() => createDraftOnly(m.proposal!)}
                        >
                          Save Draft
                        </button>
                        <button
                          className="btn btn-primary"
                          style={{ fontSize: 11.5 }}
                          onClick={() => executeCampaignAutonomously(m.proposal!)}
                        >
                          ⚡ Run Autonomous Agent
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Agent execution logs */}
              {m.agentLogs && (
                <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 6 }}>
                  <div className="mono" style={{ background: "var(--ink)", color: "#74f774", padding: 12, borderRadius: "var(--r)", fontSize: 11.5, lineHeight: 1.6 }}>
                    {m.agentLogs.map((log, idx) => (
                      <div key={idx}>{log}</div>
                    ))}
                    {m.isExecuting && (
                      <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 4 }}>
                        <span className="live"><span className="beacon" /> Running...</span>
                      </div>
                    )}
                  </div>

                  {m.finishedCampaign && (
                    <button
                      className="btn btn-primary"
                      style={{ alignSelf: "flex-start", marginTop: 8 }}
                      onClick={() => onApproved(m.finishedCampaign!.id)}
                    >
                      View Real-Time Delivery Feed →
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div style={{ alignSelf: "flex-start" }}>
            <span className="eyebrow" style={{ fontSize: 9, marginBottom: 4, display: "block" }}>Lumen Assistant</span>
            <div className="panel" style={{ padding: "10px 14px", fontStyle: "italic", color: "var(--muted)", fontSize: 13 }}>
              Thinking and drafting campaign...
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Suggested prompts helper */}
      {messages.length === 1 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, margin: "10px 0" }}>
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              className="btn"
              style={{ fontSize: 11.5 }}
              onClick={() => sendGoal(s)}
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
            padding: "8px 12px",
            borderColor: "var(--s-failed)",
            color: "var(--s-failed)",
            fontSize: 13,
            marginBottom: 8,
          }}
        >
          {error}
        </div>
      )}

      {/* Input container */}
      <div style={{ display: "flex", gap: 8, padding: "10px 0", borderTop: "1px solid var(--line)" }}>
        <input
          className="field"
          placeholder="Ask me to create a campaign, e.g. Win back lapsed customers"
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") sendGoal(goal);
          }}
          disabled={loading}
        />
        <button
          className="btn btn-primary"
          onClick={() => sendGoal(goal)}
          disabled={loading || !goal.trim()}
        >
          Send
        </button>
      </div>
    </div>
  );
}
