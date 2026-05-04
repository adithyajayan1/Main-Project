# Feature Implementation Guide

This document describes how the following features are implemented in the FormFlex application:

1. [Dashboard](#1-dashboard)
2. [Video Recording with Browser Download](#2-video-recording-with-browser-download)
3. [User Login & Registration](#3-user-login--registration)
4. [Report Graphs](#4-report-graphs)
5. [Plank Elevation Detection Bug Fix](#5-plank-elevation-detection-bug-fix)

---

## Database Schema

Two tables, auto-created by SQLAlchemy on first backend startup.

### `users`
| Column | Type | Details |
|---|---|---|
| `id` | Integer | Primary key |
| `email` | String | Unique, indexed |
| `password_hash` | String | SHA-256 hash (no salt) |
| `name` | String | Display name |
| `created_at` | DateTime | UTC timestamp |

### `sessions`
| Column | Type | Details |
|---|---|---|
| `id` | Integer | Primary key |
| `user_id` | Integer | FK → users.id |
| `exercise` | String | `pushup` / `squat` / `lunges` / `plank` |
| `rep_count` | Integer | Reps completed, or seconds held (plank) |
| `duration` | Integer | Estimated seconds: `rep_count × 3` for reps, `rep_count` for plank |
| `video_path` | String | Nullable — legacy column, no longer written to |
| `created_at` | DateTime | UTC timestamp |

```python
# models.py
DATABASE_URL = "postgresql://..."  # Supabase connection string

class User(Base):
    __tablename__ = "users"
    id            = Column(Integer, primary_key=True, index=True)
    email         = Column(String, unique=True, index=True)
    password_hash = Column(String)
    name          = Column(String)
    created_at    = Column(DateTime, default=datetime.utcnow)
    sessions      = relationship("Session", back_populates="user")

    def set_password(self, password):
        self.password_hash = hashlib.sha256(password.encode()).hexdigest()

    def verify_password(self, password):
        return self.password_hash == hashlib.sha256(password.encode()).hexdigest()

class Session(Base):
    __tablename__ = "sessions"
    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id"))
    exercise   = Column(String)
    rep_count  = Column(Integer)
    duration   = Column(Integer, nullable=True)
    video_path = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    user       = relationship("User", back_populates="sessions")
```

---

## 1. Dashboard

### Overview
Home screen after login. Displays workout stats and recent session history. Fetches from the backend on mount.

### Implementation

**Frontend (`frontend/src/pages/DashboardPage.js`)**
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

**Backend (`backend.py` — `GET /api/dashboard/{user_id}`)**
```python
@app.get("/api/dashboard/{user_id}")
def get_dashboard(user_id: int, db = Depends(get_db)):
    sessions = db.query(Session).filter(Session.user_id == user_id).order_by(Session.created_at.desc()).all()
    total_minutes = sum(s.duration or 0 for s in sessions) // 60
    return {
        "stats": {
            "streak": 1 if sessions else 0,          # simplified
            "total_workouts": len(sessions),
            "total_minutes": total_minutes,
            "this_week": len([s for s in sessions if (datetime.now() - s.created_at).days <= 7])
        },
        "recent_sessions": [serialize(s) for s in sessions[:5]]
    }
```

---

## 2. Video Recording with Browser Download

### Overview
Records the workout session from a hidden canvas (which has the processed pose frame + rep/time overlay drawn onto it) using the `MediaRecorder` API. When the session ends — either via target reached or manual stop — the recording is downloaded directly to the user's browser as MP4 (or WebM fallback). No video is stored on the server.

### MIME type detection
At session start, the preferred format is MP4 (supported by Safari and Chrome 130+). Firefox falls back to WebM.

```javascript
// WorkoutPage.js — startSession()
const mimeType = MediaRecorder.isTypeSupported('video/mp4') ? 'video/mp4' : 'video/webm';
recordingMimeRef.current = mimeType;
const mediaRecorder = new MediaRecorder(canvasStream, { mimeType });
mediaRecorder.ondataavailable = (e) => {
  if (e.data.size > 0) videoChunksRef.current.push(e.data);
};
mediaRecorder.start(1000); // 1s chunks
```

### Canvas overlays drawn per frame (visible in recording)
- Top-left: `REPS: N` (or `TIME: Ns` for plank) in green Orbitron
- Bottom strip: live feedback message in colour-coded text

```javascript
// ws.onmessage — drawn onto recordCanvasRef
ctx.fillText(selected === 'plank' ? `TIME: ${data.count}s` : `REPS: ${data.count}`, 20, 50);
// feedback bar at bottom...
```

### Save and download
```javascript
// WorkoutPage.js — saveAndDownload(exercise, count, duration)
const saveAndDownload = (exerciseName, finalCount, duration) => {
  if (mediaRecorderRef.current?.state !== "inactive") mediaRecorderRef.current.stop();

  // 1. POST metadata to backend for stats
  fetch('http://localhost:8000/api/sessions', {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ exercise: exerciseName, rep_count: finalCount, duration }),
  });

  // 2. Download video to browser
  setTimeout(() => {
    const mimeType = recordingMimeRef.current || 'video/webm';
    const ext = mimeType === 'video/mp4' ? 'mp4' : 'webm';
    const blob = new Blob(videoChunksRef.current, { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `workout_${exerciseName}_${finalCount}reps_${Date.now()}.${ext}`;
    a.click();
    URL.revokeObjectURL(url);
  }, 500);
};
```

**Backend (`backend.py` — `POST /api/sessions`)** — accepts JSON only, no file upload:
```python
class SessionRequest(BaseModel):
    exercise: str
    rep_count: int
    duration: Optional[int] = None

@app.post("/api/sessions")
async def create_session(req: SessionRequest, authorization: str = Header(...), db = Depends(get_db)):
    user_id = verify_token(authorization.replace("Bearer ", ""))
    session = Session(
        user_id=user_id, exercise=req.exercise,
        rep_count=req.rep_count, duration=req.duration,
        created_at=datetime.now()
    )
    db.add(session); db.commit()
    return {"session_id": session.id, "status": "saved"}
```

### Completion modal (target reached)
When `count >= targetReps`, instead of immediately saving, the session tears down and a modal appears with:
- Exercise name, rep/time count, estimated duration
- **SAVE & DOWNLOAD** → calls `saveAndDownload()` then closes modal
- **DISCARD** → closes modal without saving

Manual "STOP & SAVE" button skips the modal and saves immediately.

---

## 3. User Login & Registration

### Overview
JWT-based authentication. Token stored in `localStorage`. Protected pages (`workout`, `dashboard`, `reports`) redirect to login if no user in state.

### Backend
```python
SECRET_KEY = "your-secret-key-change-in-production"
ALGORITHM  = "HS256"

def create_token(user_id: int) -> str:
    payload = { "user_id": user_id, "exp": datetime.utcnow() + timedelta(days=7) }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str) -> int:
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    return payload["user_id"]  # raises HTTPException 401 on failure

@app.post("/api/auth/register")  # body: { email, password, name }
@app.post("/api/auth/login")     # body: { email, password }
# both return: { token, user: { id, email, name } }
```

### Frontend
```javascript
// LoginPage.js
const handleSubmit = async (e) => {
  e.preventDefault();
  const endpoint = isRegister ? '/api/auth/register' : '/api/auth/login';
  const res = await fetch(`http://localhost:8000${endpoint}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(isRegister ? { email, password, name } : { email, password })
  });
  if (res.ok) {
    const data = await res.json();
    localStorage.setItem('token', data.token);
    localStorage.setItem('user', JSON.stringify(data.user));
    onLogin(data.user);  // navigates to dashboard
  }
};
```

### Session persistence across reloads
```javascript
// App.js — on mount
useEffect(() => {
  const storedUser = localStorage.getItem('user');
  if (storedUser) setUser(JSON.parse(storedUser));
}, []);
```

---

## 4. Report Graphs

### Overview
Progress visualisation with week/month/year time range selector. Two Chart.js charts + total stats.

### Backend (`GET /api/reports/{user_id}?range=week|month|year`)
```python
# Fills every day in range with 0 (no gaps in line chart)
num_days = 7 if range == "week" else (30 if range == "month" else 365)
today = datetime.now().date()
labels = [(today - timedelta(days=num_days - 1 - i)).strftime("%Y-%m-%d") for i in range(num_days)]
session_counts = [date_counts.get(d, 0) for d in labels]

# Best streak — all-time, consecutive active days
active_days = sorted({s.created_at.date() for s in all_sessions}, reverse=True)
# iterates counting runs of consecutive days...

total_time = round(sum(s.duration or 0 for s in sessions) / 60, 1)  # minutes, 1 decimal
```

### Frontend (`ReportsPage.js`)
- **Line chart** — sessions per day, filled, tension 0.4, sage green (`#00e676`)
- **Doughnut chart** — exercise distribution by session count
- **Stat cards** — Total Sessions, Total Reps, Total Time (MIN), Best Streak (DAYS)

```javascript
// ChartJS registration
ChartJS.register(CategoryScale, LinearScale, BarElement, LineElement, PointElement, ArcElement, Title, Tooltip, Legend);

const sessionsChartData = {
  labels: chartData?.labels || [],
  datasets: [{
    label: 'Sessions Completed',
    data: chartData?.sessions || [],
    backgroundColor: 'rgba(0, 230, 118, 0.2)',
    borderColor: 'rgba(0, 230, 118, 1)',
    fill: true, tension: 0.4
  }]
};
```

---

## 5. Plank Elevation Detection Bug Fix

### Problem
When lying flat on the floor, the shoulder→hip→ankle body line forms ~180°, which falls inside the valid plank range (165–185°). The code had no way to distinguish a real plank (body elevated off the floor on arms/elbows) from simply lying flat, because it only measured body straightness — not elevation.

### Root cause
The inclination check (`ang((shoulder, ankle), (ankle, vertical_ref))`) correctly rejects vertical postures but passes anything horizontal — including lying flat.

### Fix
In a real plank viewed from the side, the shoulder is raised off the ground, so its Y pixel coordinate is **smaller** than the ankle's Y pixel coordinate (Y increases downward in image coordinates). When lying flat, shoulder and ankle Y values are nearly equal.

Added `MIN_ELEVATION = 40` threshold: `ankle[1] - shoulder[1]` must be ≥ 40 pixels for the plank to be considered elevated.

```python
# src/exercises/plank.py
MIN_ELEVATION = 40  # ankle y must exceed shoulder y by this much

# In process():
elevation = ankle[1] - shoulder[1]
if elevation < MIN_ELEVATION:
    feedbacks.append(("Get into plank position!", "red"))
    is_form_valid = False
```

This check runs before the timer logic, so the timer will not start while lying flat.

---

## Summary

| Feature | Key Files | Notes |
|---|---|---|
| Dashboard | `DashboardPage.js`, `backend.py` | Stats + recent 5 sessions |
| Video Recording | `WorkoutPage.js`, `backend.py` | Browser download MP4/WebM, metadata only to DB |
| User Login | `LoginPage.js`, `backend.py`, `models.py` | JWT, 7-day expiry, localStorage |
| Report Graphs | `ReportsPage.js`, `backend.py` | Line + doughnut, gap-filled daily labels, best streak |
| Plank Fix | `src/exercises/plank.py` | Elevation check rejects lying flat |
