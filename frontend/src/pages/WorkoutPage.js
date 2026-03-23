import { useState, useEffect, useRef, useCallback } from "react";
import { EXERCISES, WS_URL, COLOR } from "../constants";
import { S } from "../styles";

const speak = (text) => {
  if (!window.speechSynthesis) return;
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.rate = 1.05; u.pitch = 1.0; u.volume = 1.0;
  window.speechSynthesis.speak(u);
};

export default function WorkoutPage({ initialExercise, voiceOn, wsStatus, setWsStatus }) {
  const [selected, setSelected]             = useState(initialExercise || null);
  const [running, setRunning]               = useState(false);
  const [count, setCount]                   = useState(0);
  const [stage, setStage]                   = useState("--");
  const [depthPct, setDepthPct]             = useState(0);
  const [feedbacks, setFeedbacks]           = useState([]);
  const [processedFrame, setProcessedFrame] = useState(null);
  const [camError, setCamError]             = useState(null);
  const [lastSpoken, setLastSpoken]         = useState("");
  const [flashCount, setFlashCount]         = useState(false);

  const videoRef    = useRef(null);
  const canvasRef   = useRef(null);
  const wsRef       = useRef(null);
  const streamRef   = useRef(null);
  const intervalRef = useRef(null);
  const prevCount   = useRef(0);

  useEffect(() => () => stopSession(), []);

  // Flash + speak on new rep
  useEffect(() => {
    if (count > prevCount.current) {
      setFlashCount(true);
      setTimeout(() => setFlashCount(false), 400);
      if (voiceOn) speak(`${count}`);
    }
    prevCount.current = count;
  }, [count, voiceOn]);

  // Speak warning/error feedback when it changes
  useEffect(() => {
    if (!voiceOn || feedbacks.length === 0) return;
    const [msg, color] = feedbacks[0];
    if ((color === "red" || color === "orange") && msg !== lastSpoken) {
      speak(msg);
      setLastSpoken(msg);
    }
  }, [feedbacks, voiceOn, lastSpoken]);

  // ── Camera ────────────────────────────────────────────────────────────────
  const startCamera = () => new Promise((resolve, reject) => {
    navigator.mediaDevices
      .getUserMedia({ video: { width: 640, height: 480 } })
      .then((stream) => {
        streamRef.current = stream;
        const video = videoRef.current;
        if (!video) { reject(new Error("videoRef not ready")); return; }
        video.srcObject = stream;
        video.onloadedmetadata = () => video.play().then(resolve).catch(reject);
      })
      .catch(reject);
  });

  const stopCamera = () => {
    streamRef.current?.getTracks().forEach(t => t.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
  };

  const captureFrame = useCallback(() => {
    const video  = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || video.readyState < 2) return null;
    const w = video.videoWidth || 640;
    const h = video.videoHeight || 480;
    if (!w || !h) return null;
    canvas.width = w; canvas.height = h;
    canvas.getContext("2d").drawImage(video, 0, 0, w, h);
    return canvas.toDataURL("image/jpeg", 0.7);
  }, []);

  // ── Session ───────────────────────────────────────────────────────────────
  const startSession = async () => {
    if (!selected) return;
    setCamError(null);
    setCount(0); setStage("--"); setDepthPct(0);
    setFeedbacks([]); setProcessedFrame(null); setLastSpoken("");
    prevCount.current = 0;
    setWsStatus("connecting");

    try { await startCamera(); }
    catch {
      setCamError("Camera access denied. Please allow camera permissions.");
      setWsStatus("error");
      return;
    }

    const ws = new WebSocket(`${WS_URL}/${selected}`);
    wsRef.current = ws;

    ws.onopen = () => {
      setWsStatus("connected");
      setRunning(true);
      if (voiceOn) speak(`Starting ${EXERCISES.find(e => e.id === selected)?.label}`);
      setTimeout(() => {
        intervalRef.current = setInterval(() => {
          if (ws.readyState !== WebSocket.OPEN) return;
          const frame = captureFrame();
          if (frame) ws.send(JSON.stringify({ frame }));
        }, 100);
      }, 600);
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
      } catch (err) { console.error(err); }
    };

    ws.onerror = () => setWsStatus("error");
    ws.onclose = () => { setWsStatus("idle"); setRunning(false); };
  };

  const stopSession = () => {
    clearInterval(intervalRef.current);
    window.speechSynthesis?.cancel();
    wsRef.current?.close();
    wsRef.current = null;
    stopCamera();
    setRunning(false);
    setWsStatus("idle");
    setProcessedFrame(null);
  };

  const resetCount = () => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "reset" }));
    }
    setCount(0); setStage("--"); setDepthPct(0);
    setFeedbacks([]); setLastSpoken(""); prevCount.current = 0;
  };

  const exercise = EXERCISES.find(e => e.id === selected);

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <main style={S.main}>

      {/* Always mounted — needed for ref stability */}
      <video ref={videoRef} style={{ display: "none" }} muted playsInline autoPlay />
      <canvas ref={canvasRef} style={{ display: "none" }} />

      {/* ── Exercise selector ── */}
      {!running && (
        <section style={S.selectorWrap}>
          <p style={S.sectionLabel}>⚡ CHOOSE YOUR EXERCISE</p>

          <div style={S.grid}>
            {EXERCISES.map(ex => (
              <button
                key={ex.id}
                onClick={() => setSelected(ex.id)}
                style={S.exCard(selected === ex.id)}
              >
                <span style={S.exIcon}>{ex.icon}</span>
                <span style={S.exName}>{ex.label}</span>
                <span style={S.exDesc}>{ex.desc}</span>
                {selected === ex.id && (
                  <span style={S.exCheck}>✓ SELECTED</span>
                )}
              </button>
            ))}
          </div>

          {camError && (
            <div style={{ ...S.errorBox, margin: "0 0 20px" }}>⚠️ {camError}</div>
          )}

          <button
            onClick={startSession}
            disabled={!selected}
            style={S.startBtn(!selected)}
          >
            {selected
              ? `▶  START ${exercise?.label.toUpperCase()}`
              : "SELECT AN EXERCISE TO BEGIN"}
          </button>
        </section>
      )}

      {/* ── Active session ── */}
      {running && (
        <section style={S.session}>

          {/* Video panel */}
          <div style={S.videoPanel}>
            <div style={S.videoBox}>

              {/* Raw camera before processed frame arrives */}
              <video
                ref={(el) => {
                  if (el && streamRef.current && el.srcObject !== streamRef.current)
                    el.srcObject = streamRef.current;
                }}
                style={{
                  ...S.videoEl,
                  display: processedFrame ? "none" : "block",
                  zIndex: 1,
                }}
                muted playsInline autoPlay
              />

              {/* Annotated frame from backend */}
              {processedFrame && (
                <img
                  src={processedFrame}
                  alt="pose"
                  style={{ ...S.videoEl, zIndex: 2 }}
                />
              )}

              <div style={S.videoBadge}>
                {exercise?.icon}&nbsp;{exercise?.label.toUpperCase()}
              </div>
              <div style={S.stagePill(stage)} className="stage-badge">
                {stage}
              </div>
            </div>

            {/* Depth bar */}
            <div style={S.depthWrap}>
              <div style={S.depthRow}>
                <span style={S.depthLbl}>
                  {selected === "plank" ? "ALIGNMENT" : "DEPTH"}
                </span>
                <span style={S.depthVal(depthPct)}>{depthPct}%</span>
              </div>
              <div style={S.depthTrack}>
                <div style={S.depthFill(depthPct)} />
                <div style={S.depthMarker} />
              </div>
              <div style={S.depthHints}>
                <span>0%</span>
                <span style={{ color: "#00e676" }}>GOOD ▸ 70%</span>
                <span>100%</span>
              </div>
            </div>
          </div>

          {/* Stats panel */}
          <div style={S.statsPanel}>

            {/* Counter */}
            <div style={S.counterCard}>
              <p style={S.counterLbl}>
                {selected === "plank" ? "⏱ HOLD TIME (sec)" : "🔁 REPS"}
              </p>
              <p
                className={`counter-val${flashCount ? " flash" : ""}`}
                style={S.counterVal}
              >
                {count}
              </p>
            </div>

            {/* Feedback */}
            <div style={S.feedbackCard}>
              <div style={S.feedbackHeader}>
                <span style={S.feedbackTitle}>💬 LIVE FEEDBACK</span>
                <span style={S.voiceIndicator(voiceOn)}>
                  {voiceOn ? "🔊 SPEAKING" : "🔇 MUTED"}
                </span>
              </div>

              <div style={S.feedbackList}>
                {feedbacks.length === 0
                  ? (
                    <div style={S.waitingRow}>
                      <div style={S.waitingDot} />
                      <span style={S.waitingTxt}>Waiting for pose detection...</span>
                    </div>
                  )
                  : feedbacks.slice(0, 6).map(([msg, color], i) => (
                    <div key={`${msg}-${i}`} className="fb-row" style={S.fbRow(i === 0)}>
                      <div style={S.fbIcon(COLOR[color] || "#9e9e9e")}>
                        {color === "green" ? "✓" : color === "red" ? "✗" : color === "orange" ? "!" : "·"}
                      </div>
                      <span style={{ ...S.fbMsg, color: COLOR[color] || "#ccc" }}>
                        {msg}
                      </span>
                    </div>
                  ))
                }
              </div>
            </div>

            {/* Controls */}
            <div style={S.ctrlRow}>
              <button onClick={resetCount} style={S.resetBtn}>↺ RESET</button>
              <button onClick={stopSession} style={S.stopBtn}>■ STOP</button>
            </div>

          </div>
        </section>
      )}

      {/* Backend error */}
      {wsStatus === "error" && !camError && (
        <div style={S.errorBox}>
          ⚠️ Cannot connect to backend. Run:{" "}
          <code style={{ background: "#2a0505", padding: "2px 6px", borderRadius: 4 }}>
            uvicorn backend:app --reload --port 8000
          </code>
        </div>
      )}

    </main>
  );
}