import { useState, useEffect, useRef, useCallback } from "react";
import { EXERCISES, WS_URL, COLOR } from "../constants";
import { S } from "../styles";

export default function WorkoutPage({ initialExercise, voiceOn, wsStatus, setWsStatus, token }) {
  const [selected, setSelected]             = useState(initialExercise || null);
  const [targetReps, setTargetReps]         = useState(10);
  const [running, setRunning]               = useState(false);
  const [count, setCount]                   = useState(0);
  const [stage, setStage]                   = useState("--");
  const [depthPct, setDepthPct]             = useState(0);
  const [feedbacks, setFeedbacks]           = useState([]);
  const [processedFrame, setProcessedFrame] = useState(null);
  const [camError, setCamError]             = useState(null);
  const [flashCount, setFlashCount]         = useState(false);
  const [completionModal, setCompletionModal] = useState(null); // { count, exercise, duration }

  const videoRef    = useRef(null);
  const canvasRef   = useRef(null);
  const recordCanvasRef = useRef(null);
  const wsRef       = useRef(null);
  const streamRef   = useRef(null);
  const intervalRef = useRef(null);
  const prevCount   = useRef(0);

  // Video recording refs
  const mediaRecorderRef = useRef(null);
  const videoChunksRef = useRef([]);
  const recordingMimeRef = useRef('');

  // TTS refs
  const isSpeakingRef = useRef(false);
  const needsToSpeakRef = useRef(null);
  const currentBadPostureRef = useRef(null);
  const badPostureTimerRef = useRef(null);

  const speak = useCallback((text) => {
    if (!window.speechSynthesis) return;
    const u = new SpeechSynthesisUtterance(text);
    u.rate = 1.05; u.pitch = 1.0; u.volume = 1.0;
    
    isSpeakingRef.current = true;
    u.onend = () => {
      isSpeakingRef.current = false;
      if (needsToSpeakRef.current) {
        const nextText = needsToSpeakRef.current;
        needsToSpeakRef.current = null;
        speak(nextText);
      }
    };
    window.speechSynthesis.speak(u);
  }, []);

  useEffect(() => () => {
    stopSession();
    window.speechSynthesis?.cancel();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Flash + speak on new rep
  useEffect(() => {
    if (count > prevCount.current) {
      setFlashCount(true);
      setTimeout(() => setFlashCount(false), 400);
      if (voiceOn) speak(`${count}`);
    }
    prevCount.current = count;
  }, [count, voiceOn, speak]);

  // Show completion modal when target reached
  useEffect(() => {
    if (running && count >= targetReps && count !== 0) {
      const wait = setTimeout(() => {
        if (voiceOn) speak(`Workout complete! You reached ${targetReps}.`);
        const finalCount = prevCount.current;
        const duration = selected === 'plank' ? finalCount : Math.floor(finalCount * 3);
        teardownSession();
        setCompletionModal({ count: finalCount, exercise: selected, duration });
      }, 1000);
      return () => clearTimeout(wait);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [count, targetReps, running, voiceOn, speak]);

  // Voice feedback optimization logic
  useEffect(() => {
    if (!voiceOn) return;
    
    if (feedbacks.length === 0 || (feedbacks[0][1] !== "red" && feedbacks[0][1] !== "orange")) {
      clearTimeout(badPostureTimerRef.current);
      currentBadPostureRef.current = null;
      return;
    }

    const msg = feedbacks[0][0];

    if (currentBadPostureRef.current !== msg) {
      currentBadPostureRef.current = msg;
      clearTimeout(badPostureTimerRef.current);
      
      badPostureTimerRef.current = setTimeout(() => {
        if (!isSpeakingRef.current) {
          speak(msg);
        } else {
          needsToSpeakRef.current = msg;
        }
      }, 1000); // 1 second threshold
    }
  }, [feedbacks, voiceOn, speak]);

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
    setFeedbacks([]); setProcessedFrame(null);
    prevCount.current = 0;
    setWsStatus("connecting");
    window.speechSynthesis?.cancel();
    isSpeakingRef.current = false;
    needsToSpeakRef.current = null;
    currentBadPostureRef.current = null;
    clearTimeout(badPostureTimerRef.current);

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
      if (voiceOn) speak(`Starting ${EXERCISES.find(e => e.id === selected)?.label}. Target is ${targetReps}.`);
      
      // Start Video Recording using Canvas Stream
      if (typeof MediaRecorder !== 'undefined') {
        videoChunksRef.current = [];
        setTimeout(() => {
          if (recordCanvasRef.current) {
            try {
              const mimeType = MediaRecorder.isTypeSupported('video/mp4')
                ? 'video/mp4'
                : 'video/webm';
              recordingMimeRef.current = mimeType;
              const canvasStream = recordCanvasRef.current.captureStream(15);
              const mediaRecorder = new MediaRecorder(canvasStream, { mimeType });
              mediaRecorder.ondataavailable = (e) => {
                if (e.data.size > 0) videoChunksRef.current.push(e.data);
              };
              mediaRecorder.start(1000); // chunk every 1s
              mediaRecorderRef.current = mediaRecorder;
            } catch (err) {
              console.warn("MediaRecorder canvas initialisation failed:", err);
            }
          }
        }, 100);
      }

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

        if (recordCanvasRef.current && data.frame) {
          const img = new Image();
          img.onload = () => {
             const canvas = recordCanvasRef.current;
             const ctx = canvas.getContext('2d');
             ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
             
             // Draw rep count / plank time
             ctx.fillStyle = "#00e676";
             ctx.font = "bold 34px 'Orbitron', sans-serif";
             ctx.fillText(
               selected === 'plank'
                 ? `TIME: ${data.count || 0}s`
                 : `REPS: ${data.count || 0}`,
               20, 50
             );

             // Draw Feedback
             if (data.feedbacks && data.feedbacks.length > 0) {
                const [msg, colorStr] = data.feedbacks[0];
                const colorHex = COLOR[colorStr] || "#fff";
                ctx.fillStyle = "rgba(0,0,0,0.7)";
                ctx.fillRect(0, canvas.height - 50, canvas.width, 50);
                ctx.fillStyle = colorHex;
                ctx.font = "bold 22px 'Orbitron', sans-serif";
                ctx.fillText(`FEEDBACK: ${msg.toUpperCase()}`, 20, canvas.height - 18);
             }
          };
          img.src = data.frame;
        }
      } catch (err) { console.error(err); }
    };

    ws.onerror = () => setWsStatus("error");
    ws.onclose = () => { setWsStatus("idle"); setRunning(false); };
  };

  const saveAndDownload = (exerciseName, finalCount, duration) => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop();
    }
    if (token) {
      fetch('http://localhost:8000/api/sessions', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ exercise: exerciseName, rep_count: finalCount, duration }),
      }).catch(console.error);
    }
    setTimeout(() => {
      const chunks = videoChunksRef.current;
      if (chunks.length > 0) {
        const mimeType = recordingMimeRef.current || 'video/webm';
        const ext = mimeType === 'video/mp4' ? 'mp4' : 'webm';
        const blob = new Blob(chunks, { type: mimeType });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `workout_${exerciseName}_${finalCount}reps_${Date.now()}.${ext}`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      }
    }, 500);
  };

  const teardownSession = () => {
    clearInterval(intervalRef.current);
    wsRef.current?.close();
    wsRef.current = null;
    stopCamera();
    setRunning(false);
    setWsStatus("idle");
    setProcessedFrame(null);
  };

  // Manual stop — save immediately without modal
  const stopSession = () => {
    const currentCount = prevCount.current;
    const duration = selected === 'plank' ? currentCount : Math.floor(currentCount * 3);
    saveAndDownload(selected, currentCount, duration);
    teardownSession();
  };

  const resetCount = () => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "reset" }));
    }
    setCount(0); setStage("--"); setDepthPct(0);
    setFeedbacks([]); prevCount.current = 0;
  };

  const exercise = EXERCISES.find(e => e.id === selected);

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <main style={S.main}>

      <video ref={videoRef} style={{ display: "none" }} muted playsInline autoPlay />
      <canvas ref={canvasRef} style={{ display: "none" }} />
      {/* Hidden canvas for recording video with overlay text */}
      <canvas ref={recordCanvasRef} width={640} height={480} style={{ display: "none" }} />

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

          <div style={{ display: "flex", justifyContent: "center", marginBottom: 30, alignItems: "center", gap: 15 }}>
            <span style={{ fontSize: 13, fontWeight: "700", letterSpacing: "0.15em", color: "#c0bdb5", textTransform: "uppercase" }}>
              TARGET {selected === "plank" ? "TIME (SEC)" : "REPS"}:
            </span>
            <input 
              type="number" 
              value={targetReps} 
              onChange={e => setTargetReps(Math.max(1, Number(e.target.value)))} 
              min="1"
              max="999"
              style={{
                ...S.input,
                width: 80, 
                padding: "8px 0", 
                textAlign: "center", 
                fontSize: 20, 
                fontWeight: "700",
                color: "#3d8c6e", // Using the new theme accent color
              }}
            />
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

      {running && (
        <section style={S.session}>

          <div style={S.videoPanel}>
            <div style={S.videoBox}>

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
              
              <div style={{ position: "absolute", bottom: 12, left: 12, zIndex: 5, background: "#ff1744cc", color: "#fff", padding: "4px 8px", borderRadius: 6, fontSize: 10, fontWeight: "bold", letterSpacing: "0.1em", display: "flex", alignItems: "center", gap: 5 }}>
                <div style={{ width: 8, height: 8, borderRadius: "50%", background: "#fff", animation: "pulse-dot 1s infinite" }} />
                RECORDING
              </div>

              <div style={S.stagePill(stage)} className="stage-badge">
                {stage}
              </div>
            </div>

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

          <div style={S.statsPanel}>
            <div style={S.counterCard}>
              <p style={S.counterLbl}>
                {selected === "plank" ? "⏱ HOLD TIME (sec)" : "🔁 REPS"} / {targetReps}
              </p>
              <p
                className={`counter-val${flashCount ? " flash" : ""}`}
                style={S.counterVal}
              >
                {count}
              </p>
            </div>

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

            <div style={S.ctrlRow}>
              <button onClick={resetCount} style={S.resetBtn}>↺ RESET</button>
              <button onClick={stopSession} style={S.stopBtn}>■ STOP & SAVE</button>
            </div>

          </div>
        </section>
      )}

      {wsStatus === "error" && !camError && (
        <div style={S.errorBox}>
          ⚠️ Cannot connect to backend. Run:{" "}
          <code style={{ background: "#2a0505", padding: "2px 6px", borderRadius: 4 }}>
            uvicorn backend:app --reload --port 8000
          </code>
        </div>
      )}

      {completionModal && (
        <div style={{
          position: "fixed", inset: 0, background: "rgba(0,0,0,0.65)",
          display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100,
        }}>
          <div style={{
            background: "#ffffff", borderRadius: 16, padding: "40px 48px",
            minWidth: 340, textAlign: "center", boxShadow: "0 8px 40px rgba(0,0,0,0.25)",
          }}>
            <div style={{ fontSize: 48, marginBottom: 8 }}>🎯</div>
            <h2 style={{ fontFamily: "'Orbitron', sans-serif", fontSize: 22, color: "#1c1c1e", marginBottom: 6 }}>
              TARGET REACHED!
            </h2>
            <p style={{ color: "#6b6b72", fontSize: 14, marginBottom: 24 }}>
              {EXERCISES.find(e => e.id === completionModal.exercise)?.label} &nbsp;·&nbsp;{" "}
              {completionModal.exercise === "plank"
                ? `${completionModal.count}s held`
                : `${completionModal.count} reps`}
              &nbsp;·&nbsp; ~{Math.round(completionModal.duration / 60) || 1} min
            </p>

            <div style={{ display: "flex", gap: 12, justifyContent: "center" }}>
              <button
                onClick={() => {
                  saveAndDownload(completionModal.exercise, completionModal.count, completionModal.duration);
                  setCompletionModal(null);
                }}
                style={{
                  background: "#3d8c6e", color: "#fff", border: "none",
                  borderRadius: 8, padding: "12px 24px", fontWeight: "700",
                  fontSize: 14, cursor: "pointer", letterSpacing: "0.05em",
                }}
              >
                SAVE & DOWNLOAD
              </button>
              <button
                onClick={() => setCompletionModal(null)}
                style={{
                  background: "#f2f1ee", color: "#1c1c1e", border: "none",
                  borderRadius: 8, padding: "12px 24px", fontWeight: "700",
                  fontSize: 14, cursor: "pointer", letterSpacing: "0.05em",
                }}
              >
                DISCARD
              </button>
            </div>
          </div>
        </div>
      )}

    </main>
  );
}