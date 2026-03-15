import { useState, useEffect, useRef, useCallback } from "react";

const EXERCISES = [
  { id: "pushup",      label: "Push Up",     icon: "💪", desc: "Side view recommended" },
  { id: "squat",       label: "Squat",        icon: "🦵", desc: "Side view recommended" },
  { id: "lunges",      label: "Lunges",       icon: "🏃", desc: "Side view recommended" },
  { id: "plank",       label: "Plank",        icon: "🧘", desc: "Side view — shows hold time" },
  { id: "shouldertap", label: "Shoulder Tap", icon: "👋", desc: "Front view recommended" },
];

const WS_URL = "ws://localhost:8000/ws";

export default function App() {
  const [selected, setSelected]   = useState(null);
  const [running, setRunning]     = useState(false);
  const [count, setCount]         = useState(0);
  const [stage, setStage]         = useState("--");
  const [depthPct, setDepthPct]   = useState(0);
  const [feedbacks, setFeedbacks] = useState([]);
  const [processedFrame, setProcessedFrame] = useState(null);
  const [wsStatus, setWsStatus]   = useState("idle");
  const [camError, setCamError]   = useState(null);

  const videoRef    = useRef(null);
  const canvasRef   = useRef(null);
  const wsRef       = useRef(null);
  const streamRef   = useRef(null);
  const intervalRef = useRef(null);

  useEffect(() => () => stopSession(), []);

  const startCamera = () => {
    return new Promise((resolve, reject) => {
      navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } })
        .then((stream) => {
          streamRef.current = stream;
          const video = videoRef.current;
          if (video) {
            video.srcObject = stream;
            video.onloadedmetadata = () => {
              video.play()
                .then(() => resolve())
                .catch(reject);
            };
          } else {
            reject(new Error("videoRef not ready"));
          }
        })
        .catch(reject);
    });
  };

  const stopCamera = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
  };

  const captureFrame = useCallback(() => {
    const video  = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return null;
    if (video.readyState < 2) return null;
    const w = video.videoWidth  || 640;
    const h = video.videoHeight || 480;
    if (w === 0 || h === 0) return null;
    canvas.width  = w;
    canvas.height = h;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(video, 0, 0, w, h);
    return canvas.toDataURL("image/jpeg", 0.7);
  }, []);

  const startSession = async () => {
    if (!selected) return;
    setCamError(null);
    setCount(0); setStage("--"); setDepthPct(0);
    setFeedbacks([]); setProcessedFrame(null);
    setWsStatus("connecting");

    try {
      await startCamera();
    } catch (err) {
      console.error("Camera error:", err);
      setCamError("Camera access denied or not available. Please allow camera permissions.");
      setWsStatus("error");
      return;
    }

    const ws = new WebSocket(`${WS_URL}/${selected}`);
    wsRef.current = ws;

    ws.onopen = () => {
      setWsStatus("connected");
      setRunning(true);
      setTimeout(() => {
        intervalRef.current = setInterval(() => {
          if (ws.readyState !== WebSocket.OPEN) return;
          try {
            const frame = captureFrame();
            if (frame) ws.send(JSON.stringify({ frame }));
          } catch (e) {
            console.error("Frame capture error:", e);
          }
        }, 100);
      }, 500);
    };

    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data.error) { setWsStatus("error"); return; }
        setProcessedFrame(data.frame);
        setCount(data.count);
        setStage(data.stage);
        setDepthPct(data.depth_pct);
        setFeedbacks(data.feedbacks || []);
      } catch (e) {
        console.error("WS message parse error:", e);
      }
    };

    ws.onerror = (e) => { console.error("WS error:", e); setWsStatus("error"); };
    ws.onclose = () => { setWsStatus("idle"); setRunning(false); };
  };

  const stopSession = () => {
    clearInterval(intervalRef.current);
    if (wsRef.current) { wsRef.current.close(); wsRef.current = null; }
    stopCamera();
    setRunning(false);
    setWsStatus("idle");
    setProcessedFrame(null);
  };

  const resetCount = () => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "reset" }));
    }
    setCount(0); setStage("--"); setDepthPct(0); setFeedbacks([]);
  };

  const colorMap = {
    green: "#00e676", orange: "#ff9100", red: "#ff1744", gray: "#9e9e9e",
  };

  const exercise = EXERCISES.find(e => e.id === selected);

  return (
    <div style={styles.root}>

      {/* ── Header ── */}
      <header style={styles.header}>
        <div style={styles.logo}>
          <span style={styles.logoAccent}>FORM</span>
          <span style={styles.logoMain}>FLEX</span>
        </div>
        <div style={styles.statusDot(wsStatus)} title={wsStatus} />
      </header>

      <main style={styles.main}>

        {/* ── Always mount video + canvas so ref is ready before session starts ── */}
        <video
          ref={videoRef}
          style={{ display: "none" }}
          muted
          playsInline
          autoPlay
        />
        <canvas ref={canvasRef} style={{ display: "none" }} />

        {/* ── Exercise Selector ── */}
        {!running && (
          <section style={styles.selectorSection}>
            <p style={styles.sectionLabel}>SELECT EXERCISE</p>
            <div style={styles.exerciseGrid}>
              {EXERCISES.map(ex => (
                <button
                  key={ex.id}
                  onClick={() => setSelected(ex.id)}
                  style={styles.exerciseCard(selected === ex.id)}
                >
                  <span style={styles.exerciseIcon}>{ex.icon}</span>
                  <span style={styles.exerciseLabel}>{ex.label}</span>
                  <span style={styles.exerciseDesc}>{ex.desc}</span>
                </button>
              ))}
            </div>
            {camError && <div style={{ ...styles.errorBanner, margin: "0 0 20px 0" }}>⚠️ {camError}</div>}
            <button
              onClick={startSession}
              disabled={!selected}
              style={styles.startBtn(!selected)}
            >
              {selected ? `START ${exercise?.label.toUpperCase()}` : "SELECT AN EXERCISE"}
            </button>
          </section>
        )}

        {/* ── Active Session ── */}
        {running && (
          <section style={styles.sessionLayout}>

            {/* Left — Video */}
            <div style={styles.videoCol}>
              <div style={styles.videoWrapper}>
                {/* Show raw camera if no processed frame yet */}
                {!processedFrame && (
                  <video
                    srcObject={streamRef.current}
                    style={{ ...styles.videoImg, position: "absolute", top: 0, left: 0, zIndex: 1 }}
                    muted
                    playsInline
                    autoPlay
                    ref={(el) => {
                      if (el && streamRef.current) {
                        el.srcObject = streamRef.current;
                      }
                    }}
                  />
                )}
                {/* Processed frame from backend */}
                {processedFrame && (
                  <img
                    src={processedFrame}
                    alt="pose"
                    style={{ ...styles.videoImg, position: "absolute", top: 0, left: 0, zIndex: 2 }}
                  />
                )}
                <div style={{ ...styles.videoLabel, zIndex: 3 }}>
                  {exercise?.icon} {exercise?.label}
                </div>
              </div>
            </div>

            {/* Right — Stats */}
            <div style={styles.statsCol}>

              <div style={styles.counterCard}>
                <p style={styles.counterLabel}>
                  {selected === "plank" ? "HOLD TIME" : "REPS"}
                </p>
                <p style={styles.counterValue}>{count}</p>
                <span style={styles.stageTag(stage)}>{stage}</span>
              </div>

              {selected !== "shouldertap" && (
                <div style={styles.depthCard}>
                  <div style={styles.depthHeader}>
                    <span style={styles.depthLabel}>
                      {selected === "plank" ? "ALIGNMENT" : "DEPTH"}
                    </span>
                    <span style={styles.depthPct}>{depthPct}%</span>
                  </div>
                  <div style={styles.depthTrack}>
                    <div style={styles.depthFill(depthPct)} />
                  </div>
                </div>
              )}

              <div style={styles.feedbackCard}>
                <p style={styles.feedbackTitle}>FEEDBACK</p>
                {feedbacks.length === 0
                  ? <p style={styles.feedbackEmpty}>Waiting for pose...</p>
                  : feedbacks.slice(0, 6).map(([msg, color], i) => (
                    <div key={i} style={styles.feedbackRow}>
                      <span style={styles.feedbackDot(colorMap[color] || "#9e9e9e")} />
                      <span style={{ ...styles.feedbackMsg, color: colorMap[color] || "#ccc" }}>
                        {msg}
                      </span>
                    </div>
                  ))
                }
              </div>

              <div style={styles.controls}>
                <button onClick={resetCount} style={styles.resetBtn}>RESET</button>
                <button onClick={stopSession} style={styles.stopBtn}>STOP</button>
              </div>

            </div>
          </section>
        )}

        {wsStatus === "error" && !camError && (
          <div style={styles.errorBanner}>
            ⚠️ Cannot connect to backend. Make sure{" "}
            <code>uvicorn backend:app --reload --port 8000</code> is running.
          </div>
        )}

      </main>
    </div>
  );
}

// ── Styles ───────────────────────────────────────────────────────────────────
const styles = {
  root: {
    minHeight: "100vh",
    background: "#0a0a0f",
    color: "#e0e0e0",
    fontFamily: "'Rajdhani', sans-serif",
    display: "flex",
    flexDirection: "column",
  },
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "18px 36px",
    borderBottom: "1px solid #1e1e2e",
    background: "#0d0d18",
  },
  logo: { letterSpacing: "0.12em", fontSize: 28 },
  logoAccent: { color: "#00e676", fontWeight: 800 },
  logoMain:   { color: "#ffffff", fontWeight: 300 },
  statusDot: (status) => ({
    width: 10, height: 10, borderRadius: "50%",
    background:
      status === "connected"  ? "#00e676" :
      status === "connecting" ? "#ff9100" :
      status === "error"      ? "#ff1744" : "#444",
    boxShadow: status === "connected" ? "0 0 8px #00e676" : "none",
    transition: "all 0.3s",
  }),
  main: { flex: 1, padding: "32px 36px" },

  selectorSection: { maxWidth: 860, margin: "0 auto" },
  sectionLabel: { fontSize: 11, letterSpacing: "0.2em", color: "#555", marginBottom: 16 },
  exerciseGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(148px, 1fr))",
    gap: 12, marginBottom: 32,
  },
  exerciseCard: (active) => ({
    background: active ? "#0d2818" : "#111118",
    border: `1px solid ${active ? "#00e676" : "#1e1e2e"}`,
    borderRadius: 10,
    padding: "18px 12px",
    cursor: "pointer",
    display: "flex", flexDirection: "column", alignItems: "center", gap: 6,
    transition: "all 0.2s",
    boxShadow: active ? "0 0 16px #00e67622" : "none",
  }),
  exerciseIcon:  { fontSize: 32 },
  exerciseLabel: { fontSize: 15, fontWeight: 700, color: "#fff", letterSpacing: "0.05em" },
  exerciseDesc:  { fontSize: 10, color: "#555", textAlign: "center", letterSpacing: "0.05em" },
  startBtn: (disabled) => ({
    width: "100%", padding: "16px 0",
    background: disabled ? "#1a1a1a" : "linear-gradient(90deg, #00e676, #00bfa5)",
    border: "none", borderRadius: 10,
    color: disabled ? "#444" : "#000",
    fontSize: 16, fontWeight: 800, letterSpacing: "0.15em",
    cursor: disabled ? "not-allowed" : "pointer",
    transition: "all 0.2s",
    fontFamily: "inherit",
  }),

  sessionLayout: {
    display: "grid",
    gridTemplateColumns: "1fr 340px",
    gap: 24, maxWidth: 1100, margin: "0 auto",
  },
  videoCol: { display: "flex", flexDirection: "column", gap: 12 },
  videoWrapper: {
    position: "relative", borderRadius: 14, overflow: "hidden",
    border: "1px solid #1e1e2e", background: "#050508",
    aspectRatio: "4/3",
  },
  videoImg: {
    width: "100%", height: "100%",
    objectFit: "cover", display: "block",
  },
  videoLabel: {
    position: "absolute", bottom: 12, left: 12,
    background: "#000000aa", padding: "4px 10px", borderRadius: 6,
    fontSize: 13, letterSpacing: "0.08em",
  },

  statsCol: { display: "flex", flexDirection: "column", gap: 14 },
  counterCard: {
    background: "#111118", border: "1px solid #1e1e2e",
    borderRadius: 12, padding: "20px 24px", textAlign: "center",
  },
  counterLabel: { fontSize: 11, letterSpacing: "0.2em", color: "#555", margin: 0 },
  counterValue: {
    fontSize: 72, fontWeight: 800, color: "#00e676",
    margin: "4px 0", lineHeight: 1,
    textShadow: "0 0 24px #00e67644",
  },
  stageTag: (stage) => ({
    display: "inline-block",
    padding: "3px 12px", borderRadius: 20,
    fontSize: 12, letterSpacing: "0.12em", fontWeight: 700,
    background: (stage === "UP" || stage === "HOLD") ? "#0d2818" : "#1a0d00",
    color:      (stage === "UP" || stage === "HOLD") ? "#00e676" : "#ff9100",
    border: `1px solid ${(stage === "UP" || stage === "HOLD") ? "#00e676" : "#ff9100"}`,
  }),
  depthCard: {
    background: "#111118", border: "1px solid #1e1e2e",
    borderRadius: 12, padding: "16px 20px",
  },
  depthHeader: { display: "flex", justifyContent: "space-between", marginBottom: 10 },
  depthLabel: { fontSize: 11, letterSpacing: "0.2em", color: "#555" },
  depthPct:   { fontSize: 13, color: "#00e676", fontWeight: 700 },
  depthTrack: { height: 8, background: "#1e1e2e", borderRadius: 4, overflow: "hidden" },
  depthFill: (pct) => ({
    height: "100%", borderRadius: 4,
    width: `${pct}%`,
    background: pct > 70 ? "#00e676" : pct > 40 ? "#ff9100" : "#ff1744",
    transition: "width 0.2s, background 0.3s",
  }),
  feedbackCard: {
    background: "#111118", border: "1px solid #1e1e2e",
    borderRadius: 12, padding: "16px 20px", flex: 1,
  },
  feedbackTitle: { fontSize: 11, letterSpacing: "0.2em", color: "#555", marginBottom: 12 },
  feedbackEmpty: { fontSize: 13, color: "#333", fontStyle: "italic" },
  feedbackRow:   { display: "flex", alignItems: "center", gap: 8, marginBottom: 8 },
  feedbackDot: (color) => ({
    width: 7, height: 7, borderRadius: "50%",
    background: color, flexShrink: 0,
    boxShadow: `0 0 6px ${color}`,
  }),
  feedbackMsg: { fontSize: 13, letterSpacing: "0.04em" },
  controls: { display: "flex", gap: 10 },
  resetBtn: {
    flex: 1, padding: "12px 0",
    background: "#111118", border: "1px solid #1e1e2e",
    borderRadius: 10, color: "#aaa",
    fontSize: 13, fontWeight: 700, letterSpacing: "0.12em",
    cursor: "pointer", fontFamily: "inherit",
  },
  stopBtn: {
    flex: 1, padding: "12px 0",
    background: "#1a0505", border: "1px solid #ff1744",
    borderRadius: 10, color: "#ff1744",
    fontSize: 13, fontWeight: 700, letterSpacing: "0.12em",
    cursor: "pointer", fontFamily: "inherit",
  },
  errorBanner: {
    margin: "24px auto", maxWidth: 680,
    background: "#1a0505", border: "1px solid #ff1744",
    borderRadius: 10, padding: "14px 20px",
    color: "#ff6659", fontSize: 14, textAlign: "center",
  },
};