# Feature Implementation Guide

This document describes how the four main features are implemented in FormFlex.

1. [Dashboard](#1-dashboard)
2. [Session Recording & MP4 Download](#2-session-recording--mp4-download)
3. [User Login & Authentication](#3-user-login--authentication)
4. [Report Graphs](#4-report-graphs)

---

## 1. Dashboard

### Overview
The dashboard is the home screen after login. It shows streak, total workouts, total time, this-week count, and the 5 most recent sessions.

### Frontend (`frontend/src/pages/DashboardPage.js`)

Fetches from `/api/dashboard/{user.id}` with the stored JWT on mount. Renders stat cards and a session list.

```javascript
useEffect(() => {
  fetch(`http://localhost:8000/api/dashboard/${user.id}`, {
    headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
  })
    .then(res => res.json())
    .then(data => {
      setStats(data.stats);
      setRecentSessions(data.recent_sessions);
    });
}, [user.id]);
```

### Backend (`backend.py` — `GET /api/dashboard/{user_id}`)

Protected by `verify_token`. Computes a real consecutive-day streak from session dates, total elapsed seconds, and returns the 5 most recent sessions.

```python
@app.get("/api/dashboard/{user_id}")
def get_dashboard(user_id: int, authorization: str = Header(...), db = Depends(get_db)):
    verify_token(authorization)
    sessions = db.query(Session).filter(Session.user_id == user_id)...
    # streak: walks sorted unique session dates backwards from today
    # total_seconds: sum of session duration fields
    return {"stats": {...}, "recent_sessions": [...]}
```

---

## 2. Session Recording & MP4 Download

### Overview
The annotated video feed (with skeleton, rep count, and feedback overlays) is recorded in the browser via the `MediaRecorder` API. On stop, the WebM is uploaded to the backend, converted to MP4 by FFmpeg, and streamed back to the browser for download. No video is stored permanently on the server.

### How it works

**1. Recording (Frontend — `WorkoutPage.js`)**

A hidden canvas (`recordCanvasRef`) receives each annotated frame from the backend WebSocket response. Rep count and feedback text are drawn on top. `MediaRecorder` captures the canvas stream at 15 FPS into 1-second chunks.

```javascript
const canvasStream = recordCanvasRef.current.captureStream(15);
const mediaRecorder = new MediaRecorder(canvasStream, { mimeType: 'video/webm' });
mediaRecorder.ondataavailable = (e) => {
  if (e.data.size > 0) videoChunksRef.current.push(e.data);
};
mediaRecorder.start(1000);
```

**2. Target reached overlay**

When `count >= targetReps`, a modal overlay appears over the live session. The camera and WebSocket stay active. The user chooses:
- **KEEP GOING** — dismisses the overlay, session continues
- **STOP & SAVE** — calls `stopSession(true)`

**3. Stop & Save (Frontend)**

Only triggered when the user explicitly clicks STOP & SAVE (`shouldSave = true`). Actual elapsed seconds are tracked from `sessionStartRef`. The WebM blob is uploaded to `/api/sessions` with auth header.

```javascript
const elapsedSeconds = Math.floor((Date.now() - sessionStartRef.current) / 1000);
const formData = new FormData();
formData.append('video', blob, `session_${Date.now()}.webm`);
formData.append('exercise', selected);
formData.append('rep_count', currentCount);
formData.append('duration', elapsedSeconds);

const r = await fetch('http://localhost:8000/api/sessions', {
  method: 'POST', body: formData,
  headers: { 'Authorization': `Bearer ${token}` }
});
const { session_id } = await r.json();

// Fetch converted MP4 and trigger browser download
const mp4res = await fetch(`http://localhost:8000/api/sessions/${session_id}/download`, {
  headers: { 'Authorization': `Bearer ${token}` }
});
const mp4blob = await mp4res.blob();
const url = URL.createObjectURL(mp4blob);
const a = document.createElement('a');
a.href = url; a.download = `${selected}_${currentCount}reps.mp4`;
a.click();
```

**4. Backend conversion (`POST /api/sessions`)**

Receives the WebM, converts it to MP4 in the OS temp directory using FFmpeg, saves session metadata to the DB, and returns the `session_id`.

```python
subprocess.run([
  "ffmpeg", "-y", "-i", webm_tmp,
  "-c:v", "libx264", "-preset", "fast", "-crf", "23",
  "-c:a", "aac", mp4_tmp
])
session = Session(user_id=user_id, exercise=exercise,
                  rep_count=rep_count, duration=duration,
                  video_path=mp4_tmp, ...)
```

**5. Download (`GET /api/sessions/{session_id}/download`)**

Verifies token and confirms the requesting user owns the session, then streams the already-converted MP4 back.

```python
if session.user_id != requesting_user_id:
    raise HTTPException(status_code=403, detail="Access denied")
return FileResponse(session.video_path, media_type="video/mp4", filename=f"{exercise}_{reps}reps.mp4")
```

**Guest users** (not logged in — cannot access workout) are handled by `/api/convert` which accepts a WebM and returns an MP4 without auth.

---

## 3. User Login & Authentication

### Overview
Standard JWT-based auth. Passwords stored as SHA-256 hashes. Tokens expire after 7 days and are stored in `localStorage`.

### Database Models (`models.py`)

```python
class User(Base):
    __tablename__ = "users"
    id            = Column(Integer, primary_key=True)
    email         = Column(String, unique=True)
    password_hash = Column(String)
    name          = Column(String)
    created_at    = Column(DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = hashlib.sha256(password.encode()).hexdigest()

    def verify_password(self, password):
        return self.password_hash == hashlib.sha256(password.encode()).hexdigest()
```

### Backend (`backend.py`)

`verify_token` strips the `Bearer ` prefix internally so all callers just pass the raw `authorization` header value.

```python
SECRET_KEY = "your-secret-key-change-in-production"  # move to env var before deploying
ALGORITHM  = "HS256"

def verify_token(token: str) -> int:
    try:
        payload = jwt.decode(token.replace("Bearer ", ""), SECRET_KEY, algorithms=[ALGORITHM])
        return payload["user_id"]
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
```

### Frontend Auth Guard (`App.js`)

```javascript
const navigate = (targetPage, exerciseId = null) => {
  const authPages = ['workout', 'dashboard', 'reports'];
  if (authPages.includes(targetPage) && !user) {
    setPage("login");
    return;
  }
  setJumpTo(exerciseId);
  setPage(targetPage);
};
```

### Login Page (`LoginPage.js`)

Handles both register and login in one form. On success, stores token and user in `localStorage` and calls `onLogin(user)` to update global state.

---

## 4. Report Graphs

### Overview
Displays a line chart (sessions over time) and a doughnut chart (exercise distribution), plus a total stats card. Data is filtered by Week / Month / Year.

### Frontend (`ReportsPage.js`)

Uses `Chart.js` + `react-chartjs-2`. Fetches from `/api/reports/{user.id}?range={timeRange}` when the range selector changes.

```javascript
useEffect(() => {
  fetch(`http://localhost:8000/api/reports/${user.id}?range=${timeRange}`, {
    headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
  })
    .then(res => res.json())
    .then(data => setChartData(data));
}, [user.id, timeRange]);
```

Total time is shown as `Xm Ys` to correctly handle sessions under one minute (the backend returns both `total_time` in minutes and `total_secs` in raw seconds).

### Backend (`GET /api/reports/{user_id}`)

```python
@app.get("/api/reports/{user_id}")
def get_reports(user_id: int, range: str = "week", authorization: str = Header(...), db = Depends(get_db)):
    verify_token(authorization)
    # filter sessions by date range
    # group by date → labels + session_counts for line chart
    # group by exercise → exercises list for doughnut
    # sum rep_count and duration
    return {
        "labels": labels, "sessions": session_counts,
        "exercises": exercises,
        "total_sessions": len(sessions),
        "total_reps": total_reps,
        "total_time": total_secs // 60,
        "total_secs": total_secs,
        "best_streak": 0
    }
```

---

## Summary

| Feature | Key Files | Notes |
|---------|-----------|-------|
| Dashboard | `DashboardPage.js`, `backend.py` | Auth-protected; real consecutive-day streak |
| Recording & MP4 | `WorkoutPage.js`, `backend.py` | Canvas-based recording; FFmpeg conversion; user download only |
| Login / Auth | `LoginPage.js`, `App.js`, `backend.py`, `models.py` | JWT; `localStorage`; auth guard on 3 pages |
| Report Graphs | `ReportsPage.js`, `backend.py` | Line + doughnut charts; `total_secs` for accurate time display |
