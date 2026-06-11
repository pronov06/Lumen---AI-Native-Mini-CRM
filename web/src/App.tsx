import { useCallback, useEffect, useState } from "react";
import { api } from "./lib/api";
import { useFeed } from "./lib/useFeed";
import type { CustomerStats } from "./lib/types";
import { LiveFeed } from "./components/LiveFeed";
import { Landing } from "./screens/Landing";
import { Chat } from "./screens/Chat";
import { Compose } from "./screens/Compose";
import { Campaigns } from "./screens/Campaigns";
import { Audience } from "./screens/Audience";

type Screen = "landing" | "chat" | "compose" | "campaigns" | "audience";

const NAV: { key: Screen; label: string; num: string }[] = [
  { key: "landing", label: "Home", num: "01" },
  { key: "chat", label: "Chat Assistant", num: "02" },
  { key: "compose", label: "Co-pilot", num: "03" },
  { key: "campaigns", label: "Campaigns", num: "04" },
  { key: "audience", label: "Audience", num: "05" },
];

export default function App() {
  const [screen, setScreen] = useState<Screen>("landing");
  const [selected, setSelected] = useState<string | null>(null);
  const [stats, setStats] = useState<CustomerStats | null>(null);
  const [seeding, setSeeding] = useState(false);
  const [theme, setTheme] = useState<"light" | "dark">(
    () => (localStorage.getItem("theme") as "light" | "dark") || "light"
  );
  const feed = useFeed();

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("theme", theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme((t) => (t === "light" ? "dark" : "light"));
  };

  const refreshStats = useCallback(async () => {
    try {
      setStats(await api.customerStats());
    } catch {
      setStats(null);
    }
  }, []);

  useEffect(() => {
    refreshStats();
  }, [refreshStats]);

  const seed = async () => {
    setSeeding(true);
    try {
      await api.seed(240, 7);
      await refreshStats();
    } finally {
      setSeeding(false);
    }
  };

  const goCampaign = (id: string) => {
    setSelected(id);
    setScreen("campaigns");
  };

  const needsSeed = stats !== null && stats.total === 0;

  if (screen === "landing") {
    return <Landing onLaunch={() => setScreen("chat")} />;
  }

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "210px 1fr 380px",
        gridTemplateRows: "56px 1fr",
        height: "100vh",
      }}
    >
      {/* top bar */}
      <header
        style={{
          gridColumn: "1 / -1",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0 18px",
          borderBottom: "1px solid var(--line)",
          background: "var(--panel)",
        }}
      >
        <div
          style={{ display: "flex", alignItems: "center", gap: 11, cursor: "pointer" }}
          onClick={() => setScreen("landing")}
          title="Back to Home"
        >
          <span style={{ color: "var(--accent)", fontSize: 15 }}>◆</span>
          <span style={{ fontWeight: 700, letterSpacing: "-0.01em" }}>
            Lumen
          </span>
          <span className="eyebrow" style={{ marginTop: 1 }}>
            Engagement Console
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
          <div style={{ textAlign: "right" }}>
            <div className="label" style={{ fontSize: 10 }}>
              Audience
            </div>
            <div className="mono" style={{ fontWeight: 600 }}>
              {stats ? stats.total.toLocaleString("en-IN") : "—"}
            </div>
          </div>
          <button className="btn" onClick={seed} disabled={seeding}>
            {seeding ? "Seeding…" : stats?.total ? "Re-seed" : "Seed data"}
          </button>
          <button
            className="btn"
            onClick={toggleTheme}
            style={{
              padding: "8px 10px",
              fontSize: 12.5,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: 6,
            }}
            title={`Switch to ${theme === "light" ? "dark" : "light"} mode`}
          >
            {theme === "light" ? "🌙 Dark" : "☀️ Light"}
          </button>
        </div>
      </header>

      {/* left nav */}
      <nav
        style={{
          borderRight: "1px solid var(--line)",
          background: "var(--panel)",
          padding: "16px 10px",
          display: "flex",
          flexDirection: "column",
          gap: 2,
        }}
      >
        {NAV.map((n) => {
          const active = screen === n.key;
          return (
            <button
              key={n.key}
              className="btn-ghost"
              onClick={() => setScreen(n.key)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                padding: "9px 11px",
                border: 0,
                borderRadius: "var(--r)",
                cursor: "pointer",
                textAlign: "left",
                background: active ? "var(--accent-soft)" : "transparent",
                color: active ? "var(--accent-ink)" : "var(--ink)",
                fontWeight: active ? 600 : 500,
                fontSize: 13.5,
              }}
            >
              <span
                className="mono"
                style={{ fontSize: 10.5, color: "var(--faint)" }}
              >
                {n.num}
              </span>
              {n.label}
            </button>
          );
        })}

        <div style={{ marginTop: "auto" }}>
          <div className="label" style={{ padding: "0 11px 6px" }}>
            Feed
          </div>
          <div
            style={{
              padding: "0 11px",
              display: "flex",
              alignItems: "center",
              gap: 8,
            }}
          >
            <span
              style={{
                width: 7,
                height: 7,
                borderRadius: 999,
                background: feed.connected
                  ? "var(--accent)"
                  : "var(--s-failed)",
              }}
            />
            <span className="label">
              {feed.connected ? "connected" : "offline"}
            </span>
          </div>
        </div>
      </nav>

      {/* center workspace */}
      <main style={{ overflowY: "auto", padding: "22px 26px" }}>
        {needsSeed ? (
          <SeedPrompt onSeed={seed} seeding={seeding} />
        ) : screen === "chat" ? (
          <Chat onApproved={goCampaign} onChanged={refreshStats} />
        ) : screen === "compose" ? (
          <Compose onApproved={goCampaign} onChanged={refreshStats} />
        ) : screen === "campaigns" ? (
          <Campaigns
            feed={feed}
            selected={selected}
            onSelect={setSelected}
          />
        ) : (
          <Audience stats={stats} />
        )}
      </main>

      {/* right rail — the signature live feed, always present */}
      <aside style={{ borderLeft: "1px solid var(--line)", padding: 14, height: "100%", overflow: "hidden" }}>
        <LiveFeed feed={feed} />
      </aside>
    </div>
  );
}

function SeedPrompt({
  onSeed,
  seeding,
}: {
  onSeed: () => void;
  seeding: boolean;
}) {
  return (
    <div style={{ maxWidth: 460, marginTop: 40 }}>
      <div className="eyebrow">Empty workspace</div>
      <h1
        style={{
          fontSize: 26,
          fontWeight: 700,
          letterSpacing: "-0.02em",
          margin: "8px 0 12px",
        }}
      >
        Load the Lumen dataset
      </h1>
      <p style={{ color: "var(--muted)", marginBottom: 20 }}>
        Seeds a fictional D2C coffee brand: 240 customers with real order
        histories, computed lifecycle stages, and channel opt-ins. Nothing here
        is "John Doe" — every record has a plausible story to segment on.
      </p>
      <button className="btn btn-primary" onClick={onSeed} disabled={seeding}>
        {seeding ? "Seeding…" : "Seed data"}
      </button>
    </div>
  );
}
