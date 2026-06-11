import { useState, useEffect } from "react";

const STAGES = ["sent", "delivered", "opened", "read", "clicked"];
const COLOR: Record<string, string> = {
  sent: "var(--s-sent)",
  delivered: "var(--s-delivered)",
  opened: "var(--s-opened)",
  read: "var(--s-read)",
  clicked: "var(--s-clicked)",
  failed: "var(--s-failed)",
};
const NAMES = [
  ["Ananya K.", "whatsapp"], ["Vihaan G.", "email"], ["Diya B.", "sms"],
  ["Noah C.", "whatsapp"], ["Aditya S.", "rcs"], ["Liam P.", "email"],
  ["Krishna A.", "sms"], ["Joel S.", "whatsapp"], ["Meera R.", "email"],
  ["Kabir N.", "rcs"], ["Sara V.", "whatsapp"], ["Ishaan T.", "sms"],
  ["Riya M.", "email"], ["Arjun D.", "whatsapp"],
];
const TOTAL = NAMES.length;

type FeedRow = {
  id: string;
  name: string;
  state: string;
  time: string;
};

export function Landing({ onLaunch }: { onLaunch: () => void }) {
  const [counts, setCounts] = useState<Record<string, number>>({
    sent: 0,
    delivered: 0,
    opened: 0,
    read: 0,
    clicked: 0,
    failed: 0,
  });

  const [feedRows, setFeedRows] = useState<FeedRow[]>([]);

  // Simulation loop
  useEffect(() => {
    let timers: any[] = [];

    const hid = () => Math.random().toString(16).slice(2, 10);
    const clock = () => {
      const d = new Date();
      return d.toLocaleTimeString("en-GB", { hour12: false });
    };

    const addRow = (name: string, state: string) => {
      setFeedRows((prev) => {
        const next = [
          { id: hid(), name, state, time: clock() },
          ...prev,
        ];
        return next.slice(0, 7);
      });
    };

    const plan = (name: string, _channel: string, baseDelay: number) => {
      const seq: string[] = [];
      if (Math.random() < 0.1) {
        seq.push("failed");
      } else {
        seq.push("delivered");
        if (Math.random() < 0.62) {
          seq.push("opened");
          if (Math.random() < 0.7) {
            seq.push("read");
            if (Math.random() < 0.32) seq.push("clicked");
          }
        }
      }

      addRow(name, "sent");
      setCounts((c) => ({ ...c, sent: c.sent + 1 }));

      let t = baseDelay + 300 + Math.random() * 400;
      seq.forEach((st) => {
        const timer = setTimeout(() => {
          addRow(name, st);
          setCounts((c) => ({ ...c, [st]: c[st] + 1 }));
        }, t);
        timers.push(timer);
        t += 320 + Math.random() * 520;
      });
    };

    const run = () => {
      timers.forEach(clearTimeout);
      timers = [];
      setFeedRows([]);
      setCounts({
        sent: 0,
        delivered: 0,
        opened: 0,
        read: 0,
        clicked: 0,
        failed: 0,
      });

      NAMES.forEach(([name, channel], i) => {
        const timer = setTimeout(() => {
          plan(name, channel, 0);
        }, 140 * i + Math.random() * 120);
        timers.push(timer);
      });

      const loopTimer = setTimeout(run, 11000);
      timers.push(loopTimer);
    };

    run();

    return () => {
      timers.forEach(clearTimeout);
    };
  }, []);

  // Intersection Observer for Scroll Reveal
  useEffect(() => {
    const obs = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            e.target.classList.add("in");
            obs.unobserve(e.target);
          }
        });
      },
      { threshold: 0.16 }
    );
    document.querySelectorAll(".reveal").forEach((el) => obs.observe(el));

    return () => obs.disconnect();
  }, []);

  return (
    <div className="landing-page-root">
      {/* Scope component specific styles */}
      <style dangerouslySetInnerHTML={{ __html: `
        .landing-page-root {
          background: var(--paper);
          color: var(--ink);
          font-family: "Space Grotesk", ui-sans-serif, system-ui, sans-serif;
          font-size: 16px;
          line-height: 1.5;
          -webkit-font-smoothing: antialiased;
          text-rendering: optimizeLegibility;
          min-height: 100vh;
          overflow-x: hidden;

          --ember: #b5470b;
          --ember-ink: #8f3d06;
          --ember-soft: #f6e7d8;

          --roast: #1a1611;
          --roast-2: #221c15;
          --roast-line: #382f24;
          --roast-ink: #efe9df;
          --roast-muted: #a99f8d;
        }
        
        .landing-page-root .wrap { max-width: 1180px; margin: 0 auto; padding: 0 28px; }

        /* ---------- nav ---------- */
        .landing-page-root .nav {
          position: sticky; top: 0; z-index: 50;
          background: rgba(250, 249, 245, 0.82);
          backdrop-filter: blur(8px);
          border-bottom: 1px solid var(--line);
        }
        [data-theme='dark'] .landing-page-root .nav {
          background: rgba(15, 14, 11, 0.82);
        }
        .landing-page-root .nav-inner {
          height: 60px; display: flex; align-items: center; justify-content: space-between;
        }
        .landing-page-root .brand { display: flex; align-items: center; gap: 10px; font-weight: 700; letter-spacing: -0.01em; font-size: 17px; }
        .landing-page-root .brand .mk { color: var(--accent); font-size: 15px; }
        .landing-page-root .nav-links { display: flex; align-items: center; gap: 26px; }
        .landing-page-root .nav-links a:not(.btn) { font-size: 14px; color: var(--muted); transition: color 0.15s; }
        .landing-page-root .nav-links a:not(.btn):hover { color: var(--ink); }
        .landing-page-root .btn {
          display: inline-flex; align-items: center; gap: 8px;
          font-family: inherit; font-size: 14px; font-weight: 500;
          padding: 9px 16px; border-radius: 5px; cursor: pointer;
          border: 1px solid var(--line-strong); background: var(--panel); color: var(--ink);
          transition: background 0.14s, border-color 0.14s, transform 0.05s;
        }
        .landing-page-root .btn:hover { background: var(--panel-2); }
        .landing-page-root .btn:active { transform: translateY(0.5px); }
        .landing-page-root .btn-primary { background: var(--accent); border-color: var(--accent); color: #fff; }
        .landing-page-root .btn-primary:hover { background: var(--accent-ink); }
        .landing-page-root .nav .btn { padding: 7px 14px; }

        /* ---------- hero ---------- */
        .landing-page-root .hero { padding: 70px 0 64px; border-bottom: 1px solid var(--line); }
        .landing-page-root .hero-grid {
          display: grid; grid-template-columns: 1.05fr 0.95fr; gap: 54px; align-items: center;
        }
        .landing-page-root .h1 {
          font-size: clamp(38px, 5.4vw, 64px); line-height: 1.02; letter-spacing: -0.03em;
          font-weight: 700; margin: 18px 0 0; color: var(--ink);
        }
        .landing-page-root .h1 em { font-style: normal; color: var(--accent); }
        .landing-page-root .lede { font-size: 18px; color: var(--muted); max-width: 30em; margin: 20px 0 28px; }
        .landing-page-root .hero-cta { display: flex; gap: 12px; flex-wrap: wrap; }
        .landing-page-root .chips { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 30px; }
        .landing-page-root .chip {
          font-family: var(--font-mono); font-size: 11.5px; letter-spacing: 0.02em;
          color: var(--muted); padding: 5px 11px; border: 1px solid var(--line);
          border-radius: 999px; background: var(--panel);
        }
        .landing-page-root .chip b { color: var(--accent-ink); font-weight: 600; }

        /* ---------- live console (signature) ---------- */
        .landing-page-root .console {
          background: var(--panel); border: 1px solid var(--line-strong); border-radius: 10px;
          box-shadow: var(--shadow);
          overflow: hidden;
        }
        .landing-page-root .console-bar {
          display: flex; align-items: center; justify-content: space-between;
          padding: 11px 15px; border-bottom: 1px solid var(--line); background: var(--panel-2);
        }
        .landing-page-root .console-bar .label { font-family: var(--font-mono); font-size: 10.5px; letter-spacing: 0.14em; text-transform: uppercase; color: var(--faint); }
        .landing-page-root .live { display: inline-flex; align-items: center; gap: 7px; font-family: var(--font-mono); font-size: 10.5px; letter-spacing: 0.12em; text-transform: uppercase; color: var(--accent-ink); }
        .landing-page-root .beacon { width: 7px; height: 7px; border-radius: 999px; background: var(--accent); box-shadow: 0 0 0 0 rgba(181,71,11,0.5); animation: pulse 1.8s infinite; }
        @keyframes pulse { 0%{box-shadow:0 0 0 0 rgba(181,71,11,0.45);} 70%{box-shadow:0 0 0 7px rgba(181,71,11,0);} 100%{box-shadow:0 0 0 0 rgba(181,71,11,0);} }

        .landing-page-root .feed { height: 246px; overflow: hidden; position: relative; }
        .landing-page-root .feed-row {
          display: grid; grid-template-columns: auto auto 1fr auto; gap: 10px; align-items: center;
          padding: 8px 15px; border-bottom: 1px solid var(--line); font-size: 12.5px;
        }
        .landing-page-root .feed-row .t { font-family: var(--font-mono); color: var(--faint); font-size: 11.5px; }
        .landing-page-root .feed-row .id { font-family: var(--font-mono); color: var(--muted); font-size: 11.5px; }
        .landing-page-root .feed-row .ch { font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.03em; color: var(--muted); }
        
        .landing-page-root .pill {
          display: inline-flex; align-items: center; gap: 5px; font-family: var(--font-mono);
          font-size: 10px; letter-spacing: 0.06em; text-transform: uppercase;
          padding: 2px 7px 2px 6px; border-radius: 999px; border: 1px solid currentColor; white-space: nowrap;
        }
        .landing-page-root .pill .dot { width: 5px; height: 5px; border-radius: 999px; background: currentColor; }

        .landing-page-root .funnel { padding: 13px 15px; border-top: 1px solid var(--line); background: var(--panel-2); display: grid; gap: 9px; }
        .landing-page-root .frow { display: grid; grid-template-columns: 64px 1fr 30px; gap: 10px; align-items: center; }
        .landing-page-root .frow .fl { font-family: var(--font-mono); font-size: 10.5px; letter-spacing: 0.05em; color: var(--muted); }
        .landing-page-root .ftrack { height: 6px; background: var(--line); border-radius: 999px; overflow: hidden; }
        .landing-page-root .fbar { height: 100%; border-radius: 999px; transition: width 0.5s cubic-bezier(.2,.7,.2,1); }
        .landing-page-root .frow .fn { font-family: var(--font-mono); font-size: 12px; font-weight: 600; text-align: right; }

        /* ---------- sections ---------- */
        .landing-page-root section { padding: 84px 0; border-bottom: 1px solid var(--line); }
        .landing-page-root .sec-head { max-width: 40em; }
        .landing-page-root .h2 { font-size: clamp(27px, 3.2vw, 38px); line-height: 1.08; letter-spacing: -0.02em; font-weight: 700; margin: 12px 0 0; color: var(--ink); }
        .landing-page-root .sec-sub { color: var(--muted); font-size: 17px; margin-top: 14px; }

        .landing-page-root .bets { display: grid; grid-template-columns: 1fr 1fr; gap: 22px; margin-top: 44px; }
        .landing-page-root .bet { border: 1px solid var(--line); border-radius: 10px; background: var(--panel); padding: 26px; position: relative; overflow: hidden; }
        .landing-page-root .bet .num { font-family: var(--font-mono); font-size: 12px; color: var(--accent); letter-spacing: 0.1em; }
        .landing-page-root .bet h3 { font-size: 21px; letter-spacing: -0.01em; margin: 10px 0 10px; color: var(--ink); }
        .landing-page-root .bet p { color: var(--muted); font-size: 15px; margin: 0; }
        .landing-page-root .bet .tag { margin-top: 18px; display: inline-flex; font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.04em; color: var(--accent-ink); background: var(--accent-soft); padding: 4px 10px; border-radius: 999px; }

        /* ---------- dark roast band ---------- */
        .landing-page-root .roast {
          background: var(--roast);
          color: var(--roast-ink);
          border-top: 1px solid var(--roast-line);
          border-bottom: 1px solid var(--roast-line);
        }
        .landing-page-root .roast .h2 {
          color: var(--roast-ink) !important;
        }
        .landing-page-root .roast .eyebrow { color: #e69a55; }
        .landing-page-root .roast .sec-sub { color: var(--roast-muted); }
        .landing-page-root .loop {
          margin-top: 46px; display: grid; grid-template-columns: 1fr auto 1fr; gap: 0; align-items: stretch;
          border: 1px solid var(--roast-line); border-radius: 12px; overflow: hidden; background: var(--roast-2);
        }
        .landing-page-root .node { padding: 26px 24px; }
        .landing-page-root .node .nlabel { font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.12em; text-transform: uppercase; color: #e69a55; }
        .landing-page-root .node h4 { font-size: 18px; margin: 10px 0 12px; letter-spacing: -0.01em; color: var(--roast-ink); }
        .landing-page-root .node ul { margin: 0; padding: 0; list-style: none; display: grid; gap: 7px; }
        .landing-page-root .node li { font-family: var(--font-mono); font-size: 12.5px; color: var(--roast-muted); padding-left: 16px; position: relative; }
        .landing-page-root .node li::before { content: "→"; position: absolute; left: 0; color: #e69a55; }
        .landing-page-root .wire { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 0 8px; border-left: 1px solid var(--roast-line); border-right: 1px solid var(--roast-line); background: rgba(0,0,0,0.12); min-width: 132px; }
        .landing-page-root .wire .w { font-family: var(--font-mono); font-size: 10px; letter-spacing: 0.06em; color: var(--roast-muted); text-align: center; white-space: nowrap; }
        .landing-page-root .wire .arrow { color: #e69a55; font-size: 17px; line-height: 1.2; }
        .landing-page-root .wire .send { color: #cb8f43; }
        .landing-page-root .props { display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px; margin-top: 26px; }
        .landing-page-root .prop { border: 1px solid var(--roast-line); border-radius: 10px; padding: 20px; background: transparent; }
        .landing-page-root .prop h5 { font-family: var(--font-mono); font-size: 12px; letter-spacing: 0.05em; color: #e69a55; margin: 0 0 8px; text-transform: uppercase; }
        .landing-page-root .prop p { margin: 0; font-size: 13.5px; color: var(--roast-muted); }

        /* ---------- scope ---------- */
        .landing-page-root .scope-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px 40px; margin-top: 40px; }
        .landing-page-root .scope-col h4 { font-family: var(--font-mono); font-size: 12px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); margin: 0 0 14px; }
        .landing-page-root .scope-list { display: grid; gap: 10px; }
        .landing-page-root .scope-item { display: flex; align-items: baseline; gap: 11px; font-size: 15px; }
        .landing-page-root .scope-item .mk { font-family: var(--font-mono); font-size: 13px; }
        .landing-page-root .is .mk { color: var(--accent); }
        .landing-page-root .isnt { color: var(--faint); }
        .landing-page-root .isnt .mk { color: var(--s-failed); }
        .landing-page-root .isnt .txt { text-decoration: none; }
        .landing-page-root a { text-decoration: none !important; }

        /* ---------- proof ---------- */
        .landing-page-root .proof { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 18px; margin-top: 40px; }
        .landing-page-root .bug { border: 1px solid var(--line); border-radius: 10px; padding: 22px; background: var(--panel); }
        .landing-page-root .bug .n { font-family: var(--font-mono); font-size: 22px; font-weight: 600; color: var(--accent); letter-spacing: -0.02em; }
        .landing-page-root .bug h4 { font-size: 15.5px; margin: 12px 0 8px; letter-spacing: -0.01em; color: var(--ink); }
        .landing-page-root .bug p { margin: 0; font-size: 13.5px; color: var(--muted); }
        .landing-page-root .proof-foot { margin-top: 22px; font-family: var(--font-mono); font-size: 13px; color: var(--accent-ink); }

        /* ---------- footer ---------- */
        .landing-page-root footer { border-top: 1px solid var(--line); padding: 56px 0 64px; background: var(--panel); }
        .landing-page-root .foot-grid { display: flex; align-items: center; justify-content: space-between; gap: 24px; flex-wrap: wrap; }
        .landing-page-root .foot-grid p { margin: 0; color: var(--muted); font-size: 14px; max-width: 34em; }
        .landing-page-root .foot-meta { font-family: var(--font-mono); font-size: 11.5px; color: var(--faint); margin-top: 26px; }

        /* Scroll Reveal classes */
        .landing-page-root .reveal { opacity: 0; transform: translateY(14px); transition: opacity 0.6s ease, transform 0.6s ease; }
        .landing-page-root .reveal.in { opacity: 1; transform: none; }

        @media (max-width: 900px) {
          .landing-page-root .hero-grid { grid-template-columns: 1fr; gap: 40px; }
          .landing-page-root .bets, .landing-page-root .props, .landing-page-root .proof, .landing-page-root .scope-grid, .landing-page-root .foot-grid { grid-template-columns: 1fr; }
          .landing-page-root .loop { grid-template-columns: 1fr; }
          .landing-page-root .wire { flex-direction: row; gap: 14px; border: 0; border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); min-width: 0; padding: 12px; }
          .landing-page-root .nav-links a:not(.btn) { display: none; }
          .landing-page-root section { padding: 60px 0; }
        }
      ` }} />

      <nav className="nav">
        <div className="wrap nav-inner">
          <a className="brand" href="#top"><span className="mk">◆</span> Lumen</a>
          <div className="nav-links">
            <a href="#bets">The bet</a>
            <a href="#loop">Architecture</a>
            <a href="#scope">Scope</a>
            <a href="#proof">Proof</a>
            <button className="btn btn-primary" onClick={onLaunch}>See the build</button>
          </div>
        </div>
      </nav>

      <main id="top">
        {/* HERO */}
        <section className="hero">
          <div className="wrap hero-grid">
            <div>
              <span className="eyebrow">AI-native engagement console</span>
              <h1 className="h1">Reach the right shoppers.<br /><em>Watch every message land.</em></h1>
              <p className="lede">
                Describe a goal in plain language. Lumen proposes the audience,
                the channel, and the message — you approve, and delivery streams
                back in real time: out of order, deduplicated, and honest about
                what failed.
              </p>
              <div className="hero-cta">
                <a className="btn btn-primary" href="#loop" style={{ background: "var(--accent)", color: "#fff", borderColor: "var(--accent)" }}>How it works</a>
                <a className="btn" href="#proof">Why it's proven</a>
              </div>
              <div className="chips">
                <span className="chip"><b>2</b> services · <b>1</b> HTTP boundary</span>
                <span className="chip">append-only event log</span>
                <span className="chip"><b>29</b> tests green</span>
                <span className="chip">effectively-once ingest</span>
              </div>
            </div>

            {/* signature: self-running delivery console */}
            <div className="console" id="console" aria-label="Live delivery feed demonstration">
              <div className="console-bar">
                <span className="label">Win-back · lapsed shoppers</span>
                <span className="live"><span className="beacon"></span> live</span>
              </div>
              
              <div className="feed" id="feed">
                {feedRows.map((row) => (
                  <div key={row.id} className="feed-row" style={{ animation: "slidein 0.45s ease" }}>
                    <span className="t">{row.time}</span>
                    <span className="id">{row.id}</span>
                    <span className="ch">{row.name}</span>
                    <span className={`pill st-${row.state}`}>
                      <span className="dot" style={{ background: COLOR[row.state] }}></span>
                      {row.state}
                    </span>
                  </div>
                ))}
              </div>

              <div className="funnel" id="funnel">
                {[...STAGES, "failed"].map((s) => (
                  <div key={s} className="frow">
                    <span className="fl">{s}</span>
                    <span className="ftrack">
                      <span
                        className="fbar"
                        style={{
                          background: COLOR[s],
                          width: `${(counts[s] / TOTAL) * 100}%`,
                        }}
                      ></span>
                    </span>
                    <span className="fn">{counts[s]}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* BETS */}
        <section id="bets">
          <div className="wrap">
            <div className="sec-head reveal">
              <span className="eyebrow">The product bet</span>
              <h2 className="h2">Two bets, built properly — not ten built shallowly.</h2>
              <p className="sec-sub">
                The brief is intentionally open. These are the choices Lumen
                commits to, and the reason everything else was left out.
              </p>
            </div>
            <div className="bets">
              <div className="bet reveal">
                <span className="num">01</span>
                <h3>The co-pilot proposes. You approve.</h3>
                <p>
                  State intent — "win back lapsed customers with a 20% offer." The
                  co-pilot returns a real plan: a segment with a live audience
                  count, a channel, and a drafted message. You edit it, and you are
                  the one who launches it. The AI never sends on its own.
                </p>
                <span className="tag">human-in-the-loop gate</span>
              </div>
              <div className="bet reveal">
                <span className="num">02</span>
                <h3>Delivery is a live, honest surface.</h3>
                <p>
                  Real messaging is asynchronous and messy — receipts arrive late,
                  duplicated, sometimes not at all. Most demos hide that behind a
                  success toast. Here every state change streams into the feed as it
                  happens, and the funnel fills in front of you.
                </p>
                <span className="tag">sent → delivered → opened → read → clicked</span>
              </div>
            </div>
          </div>
        </section>

        {/* CALLBACK LOOP */}
        <section className="roast" id="loop">
          <div className="wrap">
            <div className="sec-head reveal">
              <span className="eyebrow">System-design centerpiece</span>
              <h2 className="h2">One loop, modeled the way delivery actually works.</h2>
              <p className="sec-sub">
                Two real services that talk only over HTTP — the way a CRM talks to
                a messaging provider. Every callback is an immutable event; current
                state is a projection folded over the log.
              </p>
            </div>

            <div className="loop reveal">
              <div className="node">
                <div className="nlabel">CRM service</div>
                <h4>Owns the truth</h4>
                <ul>
                  <li>customers, orders, campaigns</li>
                  <li>segments + AI co-pilot</li>
                  <li>append-only event log</li>
                  <li>folds events → projection</li>
                  <li>WebSocket fan-out</li>
                </ul>
              </div>
              <div className="wire">
                <div className="arrow send">→</div>
                <div className="w send">POST /v1/send</div>
                <div className="w">signed callbacks</div>
                <div className="w">POST /receipts (HMAC)</div>
                <div className="arrow">←</div>
              </div>
              <div className="node">
                <div className="nlabel">Channel service</div>
                <h4>Simulates a provider</h4>
                <ul>
                  <li>probabilistic outcomes</li>
                  <li>latency + reordering</li>
                  <li>duplicate callbacks</li>
                  <li>hard failures</li>
                  <li>imports nothing from CRM</li>
                </ul>
              </div>
            </div>

            <div className="props">
              <div className="prop reveal">
                <h5>Out-of-order safe</h5>
                <p>A late <span className="mono">delivered</span> after a <span className="mono">read</span> can't move state backward — the fold respects a monotonic lifecycle rank.</p>
              </div>
              <div className="prop reveal">
                <h5>Idempotent</h5>
                <p>A unique key per event rejects duplicate callbacks at the database. At-least-once plus idempotent ingest is effectively-once.</p>
              </div>
              <div className="prop reveal">
                <h5>Auditable &amp; replayable</h5>
                <p>The log is authoritative; the fast-read projection is a cache that can always be rebuilt by re-folding.</p>
              </div>
            </div>
          </div>
        </section>

        {/* SCOPE */}
        <section id="scope">
          <div className="wrap">
            <div className="sec-head reveal">
              <span className="eyebrow">Scope discipline</span>
              <h2 className="h2">Sharp about what this is — and what it isn't.</h2>
              <p className="sec-sub">
                A marketing and engagement tool, in the spirit of reaching
                shoppers. Deliberately not a sales or support CRM.
              </p>
            </div>
            <div className="scope-grid reveal">
              <div className="scope-col">
                <h4>This is</h4>
                <div className="scope-list">
                  <div className="scope-item is"><span className="mk">+</span><span className="txt">Ingest of customers and their order histories</span></div>
                  <div className="scope-item is"><span className="mk">+</span><span className="txt">Behavioural segments, written by the co-pilot</span></div>
                  <div className="scope-item is"><span className="mk">+</span><span className="txt">Personalised sends across WhatsApp, SMS, Email, RCS</span></div>
                  <div className="scope-item is"><span className="mk">+</span><span className="txt">Live funnel and order attribution per campaign</span></div>
                </div>
              </div>
              <div className="scope-col">
                <h4>This is not</h4>
                <div className="scope-list">
                  <div className="scope-item isnt"><span className="mk">×</span><span className="txt">Deals, pipelines, leads, tickets</span></div>
                  <div className="scope-item isnt"><span className="mk">×</span><span className="txt">A drag-and-drop journey builder</span></div>
                  <div className="scope-item isnt"><span className="mk">×</span><span className="txt">A template management CMS</span></div>
                  <div className="scope-item isnt"><span className="mk">×</span><span className="txt">Auth, roles, and org administration</span></div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* PROOF */}
        <section id="proof">
          <div className="wrap">
            <div className="sec-head reveal">
              <span className="eyebrow">Proven, not promised</span>
              <h2 className="h2">The hard part was tested adversarially — and it found real bugs.</h2>
              <p className="sec-sub">
                An end-to-end test runs both services over real HTTP with the
                channel turned hostile: 60% reordering, 40% duplicates, 12%
                failures. Standing it up surfaced three genuine concurrency bugs a
                happy path would never catch.
              </p>
            </div>
            <div className="proof">
              <div className="bug reveal">
                <div className="n">01</div>
                <h4>Eager dispatch in the evaluator</h4>
                <p>A dict of comparators ran every branch, so a numeric rule hit <span className="mono">3 in 0</span> and threw. Fixed with short-circuiting comparisons.</p>
              </div>
              <div className="bug reveal">
                <div className="n">02</div>
                <h4>MissingGreenlet on duplicates</h4>
                <p>A full rollback on the idempotency conflict expired the loaded row, triggering I/O outside the async greenlet. Scoped the insert to a SAVEPOINT.</p>
              </div>
              <div className="bug reveal">
                <div className="n">03</div>
                <h4>Lost update on the cache</h4>
                <p>The worker's <span className="mono">sent</span> write raced an inbound <span className="mono">delivered</span> and clobbered it with a stale fold. Serialized per-communication with a keyed lock + row lock.</p>
              </div>
            </div>
            <p className="proof-foot">→ Final state: 29 tests green, run repeatedly to confirm stability — not a lucky pass.</p>
          </div>
        </section>
      </main>

      <footer>
        <div className="wrap">
          <div className="foot-grid">
            <p>
              Lumen is an AI-native Mini CRM built for an engineering take-home —
              a chat-first campaign co-pilot wrapped around a two-service,
              callback-driven delivery loop.
            </p>
            <a className="btn btn-primary" href="#top">Back to top</a>
          </div>
          <div className="foot-meta">
            FastAPI ×2 · Postgres / SQLite · Redis · React 18 + TypeScript ·
            OpenRouter · WebSockets
          </div>
        </div>
      </footer>
    </div>
  );
}
