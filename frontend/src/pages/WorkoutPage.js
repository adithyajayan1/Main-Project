import { useState, useEffect, useRef, useCallback } from "react";
import { EXERCISES, WS_URL, COLOR } from "../constants";
import { S } from "../styles";

const speak = (text) => {
  if (!window.speechSynthesis) {
    console.warn("Speech synthesis not supported");
    return;
  }
  // Cancel any ongoing speech first
  window.speechSynthesis.cancel();
  
  const u = new SpeechSynthesisUtterance(text);
  u.rate = 1.05; 
  u.pitch = 1.0; 
  u.volume = 1.0;
  
  // Try to get a working voice
  const voices = window.speechSynthesis.getVoices();
  if (voices.length > 0) {
    // Prefer English voices
    const englishVoice = voices.find(v => v.lang.startsWith("en")) || voices[0];
    u.voice = englishVoice;
  }
  
  // Add error handler
  u.onerror = (event) => {
    console.warn("Speech synthesis error:", event.error);
  };
  
  // Also try immediately in case browser blocks it
  try {
    window.speechSynthesis.speak(u);
  } catch (e) {
    console.warn("Failed to speak:", e);
  }
};

export default function WorkoutPage({ initialExercise, voiceOn, wsStatus, setWsStatus, navigate }) {
  // Note: navigate is passed as prop from App.js, not react-router-dom
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
  const [recording, setRecording]               = useState(false);
  const [recordedChunks, setRecordedChunks]   = useState([]);
  const [repLimit, setRepLimit]                = useState(10);

  const videoRef           = useRef(null);
  const canvasRef          = useRef(null);
  const wsRef              = useRef(null);
  const streamRef          = useRef(null);
  const intervalRef        = useRef(null);
  const prevCount          = useRef(0);
  const lastSpokenTimeRef  = useRef(0);  // Track when we last spoke for green feedback throttling
  const mediaRecorderRef   = useRef(null);

  useEffect(() => () => stopSession(), []);

  // Flash + speak on new rep - with delay to avoid interrupting feedback
  useEffect(() => {
    if (count > prevCount.current) {
      setFlashCount(true);
      setTimeout(() => setFlashCount(false), 400);
      if (voiceOn) {
        // Delay count speech slightly to allow feedback to be spoken first
        setTimeout(() => speak(`${count}`), 500);
      }
    }
    prevCount.current = count;
  }, [count, voiceOn]);

  // Auto-stop recording when rep limit is reached
  useEffect(() => {
    if (recording && count >= repLimit && repLimit > 0 && mediaRecorderRef.current?.state === "recording") {
      stopRecording();
    }
  }, [count, repLimit, recording]);

  // Speak feedback when it changes - all colors (red, orange, green, gray)
  useEffect(() => {
    if (!voiceOn || feedbacks.length === 0) return;
    
    // Find the first feedback that should be spoken (skip if already spoken)
    for (const [msg, color] of feedbacks) {
      if (msg !== lastSpoken) {
        // Speak all important feedback: red (error), orange (warning), gray (info)
        // Also speak green (positive) feedback occasionally
        if (color === "red" || color === "orange" || color === "gray") {
          speak(msg);
          setLastSpoken(msg);
          break;
        } else if (color === "green") {
          // Speak green feedback but less frequently to avoid too much speech
          // Only speak if we haven't spoken a green message in the last 3 seconds
          const timeSinceLastSpoken = Date.now() - (lastSpokenTimeRef.current || 0);
          if (timeSinceLastSpoken > 3000) {
            speak(msg);
            setLastSpoken(msg);
            lastSpokenTimeRef.current = Date.now();
            break;
          }
        }
      }
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
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
      mediaRecorderRef.current.stop();
      // Clean up recording state immediately since session is ending
      setRecording(false);
      mediaRecorderRef.current = null;
      setRecordedChunks([]);
    }
    // Clean up overlay animation
    if (recordingAnimationRef.current) {
      cancelAnimationFrame(recordingAnimationRef.current);
      recordingAnimationRef.current = null;
    }
    overlayCanvasRef.current = null;
    if (overlayStreamRef.current) {
      overlayStreamRef.current.getTracks().forEach(t => t.stop());
      overlayStreamRef.current = null;
    }
  };

  // ── Recording with visual overlay ───────────────────────────────────────────────────
  const overlayCanvasRef = useRef(null);
  const overlayStreamRef = useRef(null);
  const recordingAnimationRef = useRef(null);

  // Draw overlay on canvas (rep count + feedback)
  const drawOverlay = (ctx, width, height, count, feedbackList) => {
    
    // Rep counter in top-right corner
    ctx.fillStyle = "rgba(0, 0, 0, 0.7)";
    ctx.fillRect(width - 120, 10, 110, 60);
    ctx.font = "bold 36px Orbitron, sans-serif";
    ctx.fillStyle = "#00e676";
    ctx.textAlign = "right";
    ctx.fillText(count.toString(), width - 20, 55);
    
    // Feedback display in bottom-left corner
    if (feedbackList && feedbackList.length > 0) {
      const feedbackText = feedbackList[0][0]; // Get most recent feedback message
      ctx.fillStyle = "rgba(0, 0, 0, 0.7)";
      ctx.fillRect(10, height - 70, Math.min(width - 20, 400), 60);
      ctx.font = "bold 20px Rajdhani, sans-serif";
      
      // Color based on feedback type
      const feedbackColor = feedbackList[0][1];
      if (feedbackColor === "red") ctx.fillStyle = "#ff1744";
      else if (feedbackColor === "orange") ctx.fillStyle = "#ff9100";
      else if (feedbackColor === "green") ctx.fillStyle = "#00e676";
      else ctx.fillStyle = "#9e9e9e";
      
      ctx.textAlign = "left";
      ctx.fillText(feedbackText.substring(0, 40), 20, height - 30);
    }
  };

  // Start recording video with overlay
  const startRecording = () => {
    if (!streamRef.current) return;
    
    const video = videoRef.current;
    const width = video.videoWidth || 640;
    const height = video.videoHeight || 480;
    
    // Create overlay canvas
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    overlayCanvasRef.current = canvas;
    const ctx = canvas.getContext("2d");
    
    // Create stream from canvas
    const canvasStream = canvas.captureStream(30); // 30 FPS
    
    // Get video track from camera stream
    const videoTrack = streamRef.current.getVideoTracks()[0];
    if (videoTrack) {
      canvasStream.addTrack(videoTrack);
    }
    
    overlayStreamRef.current = canvasStream;
    
    const options = { mimeType: "video/webm;codecs=vp9" };
    if (!MediaRecorder.isTypeSupported(options.mimeType)) {
      options.mimeType = "video/webm;codecs=vp8";
      if (!MediaRecorder.isTypeSupported(options.mimeType)) {
        options.mimeType = "video/webm";
      }
    }
    
    const chunks = [];
    const mediaRecorder = new MediaRecorder(canvasStream, options);
    
    // Animation loop to draw frames with overlay
    const drawFrame = () => {
      if (!overlayCanvasRef.current || !mediaRecorderRef.current || mediaRecorderRef.current.state !== "recording") return;
      
      const c = overlayCanvasRef.current;
      const cx = c.getContext("2d");
      
      // Draw camera frame
      if (video && video.readyState >= 2) {
        cx.drawImage(video, 0, 0, c.width, c.height);
      }
      
      // Draw overlay
      drawOverlay(cx, c.width, c.height, count, feedbacks);
      
      recordingAnimationRef.current = requestAnimationFrame(drawFrame);
    };
    
    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) {
        chunks.push(e.data);
      }
    };
    
    mediaRecorder.onstop = () => {
      setRecordedChunks(chunks);
      setRecording(false);
      mediaRecorderRef.current = null;
      if (recordingAnimationRef.current) {
        cancelAnimationFrame(recordingAnimationRef.current);
      }
    };
    
    mediaRecorder.start(100);
    mediaRecorderRef.current = mediaRecorder;
    setRecording(true);
    setRecordedChunks([]);
    
    // Start the drawing loop
    drawFrame();
  };

  // Stop recording video
  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
      mediaRecorderRef.current.stop();
      // Note: recording state will be set to false in onstop callback
    }
  };

  // Download recorded video
  const downloadRecording = () => {
    if (recordedChunks.length === 0) return;
    
    const blob = new Blob(recordedChunks, { type: "video/webm" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${selected}_${new Date().toISOString().slice(0,10)}.webm`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
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
                <a
                  href={`/tutorials?id=${ex.id}`}
                  onClick={(e) => { e.preventDefault(); navigate(`/tutorials?id=${ex.id}`); }}
                  style={S.exHelpLink}
                >
                  📖 View Tutorial
                </a>
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

            {/* Recording Controls */}
            <div style={S.recordingCard}>
              <div style={S.recordingHeader}>
                <span style={S.recordingTitle}>🎬 VIDEO RECORDING</span>
              </div>
              
              <div style={S.repLimitRow}>
                <span style={S.repLimitLabel}>Stop recording after:</span>
                <input
                  type="number"
                  min="1"
                  max="100"
                  value={repLimit}
                  onChange={(e) => setRepLimit(Math.max(1, Math.min(100, parseInt(e.target.value, 10) || 10)))}
                  style={S.repLimitInput}
                />
                <span style={S.repLimitUnit}>reps</span>
              </div>

              <div style={S.recCtrlRow}>
                {!recording ? (
                  <button onClick={startRecording} style={S.recordBtn} disabled={!running}>
                    {running ? "⏺ START RECORDING" : "⏺ RECORD"}
                  </button>
                ) : (
                  <button onClick={stopRecording} style={S.recordingActiveBtn}>
                    ⏹ STOP RECORDING
                  </button>
                )}
                
                {recordedChunks.length > 0 && !recording && (
                  <button onClick={downloadRecording} style={S.downloadBtn}>
                    ↓ DOWNLOAD
                  </button>
                )}
              </div>

              {recording && (
                <div style={S.recordingStatus}>
                  <span style={S.recDot} /> Recording... (auto-stops at {repLimit} reps)
                </div>
              )}
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