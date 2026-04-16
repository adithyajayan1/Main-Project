# Feature Implementation Guide

This document describes how the following features are implemented in the GymLytics application:

1. Dashboard
2. Video Recording with Start/Stop (rep count/plank time)
3. User Login
4. Report Graphs (sessions per user)

---

## 1. Dashboard

### Overview
The dashboard serves as the home screen after user login, displaying an overview of workout statistics, recent activity, and quick access to exercises.

### Implementation

**Frontend (`frontend/src/pages/DashboardPage.js`)**

```javascript
export default function DashboardPage({ user, navigate }) {
  const [stats, setStats] = useState(null);
  const [recentSessions, setRecentSessions] = useState([]);

  useEffect(() => {
    fetch(`/api/dashboard/${user.id}`)
      .then(res => res.json())
      .then(data => {
        setStats(data.stats);
        setRecentSessions(data.recent_sessions);
      });
  }, [user.id]);

  return (
    <div style={S.dashboard}>
      {/* Welcome Header */}
      <h1>Welcome back, {user.name}!</h1>

      {/* Quick Stats Cards */}
      <div style={S.statsGrid}>
        <StatCard icon="🔥" label="Streak" value={`${stats?.streak} days`} />
        <StatCard icon="🏋️" label="Total Workouts" value={stats?.total_workouts} />
        <StatCard icon="⏱️" label="Total Time" value={formatTime(stats?.total_minutes)} />
        <StatCard icon="🎯" label="This Week" value={stats?.this_week} />
      </div>

      {/* Quick Start Section */}
      <section style={S.quickStart}>
        <h2>Quick Start</h2>
        <div style={S.exerciseButtons}>
          {EXERCISES.map(ex => (
            <button onClick={() => navigate('workout', ex.id)}>
              {ex.icon} {ex.label}
            </button>
          ))}
        </div>
      </section>

      {/* Recent Sessions */}
      <section style={S.recentSection}>
        <h2>Recent Sessions</h2>
        {recentSessions.map(session => (
          <SessionCard session={session} onClick={() => navigate('session', session.id)} />
        ))}
      </section>
    </div>
  );
}
```

**Backend API (`backend.py`)**

```python
@app.get("/api/dashboard/{user_id}")
def get_dashboard(user_id: int):
    user = db.query(User).get(user_id)
    stats = {
        "streak": calculate_streak(user_id),
        "total_workouts": count_workouts(user_id),
        "total_minutes": get_total_time(user_id),
        "this_week": count_this_week(user_id)
    }
    recent = get_recent_sessions(user_id, limit=5)
    return {"stats": stats, "recent_sessions": recent}
```

---

## 2. Video Recording with Start/Stop (Rep Count/Plank Time)

### Overview
This feature records workout sessions with video, tracking rep counts for exercises like pushups/squats/lunges and time for plank exercises.

### Implementation

**Frontend - Recording Controls (`frontend/src/pages/WorkoutPage.js`)**

```javascript
const [recording, setRecording] = useState(false);
const [videoChunks, setVideoChunks] = useState([]);
const mediaRecorderRef = useRef(null);

// Start Recording
const startRecording = () => {
  const stream = streamRef.current;
  const mediaRecorder = new MediaRecorder(stream, { mimeType: 'video/webm' });
  
  mediaRecorder.ondataavailable = (e) => {
    if (e.data.size > 0) {
      setVideoChunks(prev => [...prev, e.data]);
    }
  };

  mediaRecorder.start(1000); // Capture every second
  mediaRecorderRef.current = mediaRecorder;
  setRecording(true);
};

// Stop Recording and Save
const stopRecording = () => {
  mediaRecorderRef.current?.stop();
  setRecording(false);
  
  const blob = new Blob(videoChunks, { type: 'video/webm' });
  const formData = new FormData();
  formData.append('video', blob, `session_${Date.now()}.webm`);
  formData.append('exercise', selected);
  formData.append('rep_count', count);
  formData.append('duration', selected === 'plank' ? count : null); // plank uses count as seconds
  
  fetch('/api/sessions', {
    method: 'POST',
    body: formData,
    headers: { 'Authorization': `Bearer ${token}` }
  });
  
  setVideoChunks([]);
};

// UI Controls in Workout Page
<div style={S.controls}>
  {!recording ? (
    <button onClick={startRecording}>● START RECORDING</button>
  ) : (
    <button onClick={stopRecording}>■ STOP & SAVE</button>
  )}
</div>
```

**Backend - Session Storage (`backend.py`)**

```python
from fastapi import UploadFile, File
import os
from datetime import datetime

VIDEO_DIR = "recordings"
os.makedirs(VIDEO_DIR, exist_ok=True)

@app.post("/api/sessions")
async def create_session(
    video: UploadFile = File(...),
    exercise: str = Form(...),
    rep_count: int = Form(...),
    duration: Optional[int] = Form(None),
    token: str = Header(...)
):
    user_id = verify_token(token)
    
    # Save video file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    video_path = f"{VIDEO_DIR}/{user_id}_{exercise}_{timestamp}.webm"
    
    with open(video_path, "wb") as f:
        f.write(await video.read())
    
    # Save session to database
    session = Session(
        user_id=user_id,
        exercise=exercise,
        rep_count=rep_count,
        duration=duration,
        video_path=video_path,
        created_at=datetime.now()
    )
    db.add(session)
    db.commit()
    
    return {"session_id": session.id, "status": "saved"}
```

---

## 3. User Login

### Overview
Implements secure user authentication with JWT tokens, registration, and session management.

### Implementation

**Database Models (`models.py`)**

```python
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import hashlib

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    password_hash = Column(String)
    name = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        self.password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    def verify_password(self, password):
        return self.password_hash == hashlib.sha256(password.encode()).hexdigest()
```

**Backend Authentication (`backend.py`)**

```python
import jwt
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

SECRET_KEY = "your-secret-key-change-in-production"
ALGORITHM = "HS256"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def create_token(user_id: int) -> str:
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(days=7)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str) -> int:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload["user_id"]
    except:
        raise HTTPException(status_code=401, detail="Invalid token")

@app.post("/api/auth/register")
def register(email: str, password: str, name: str):
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user = User(email=email, name=name)
    user.set_password(password)
    db.add(user)
    db.commit()
    
    token = create_token(user.id)
    return {"token": token, "user": {"id": user.id, "email": user.email, "name": user.name}}

@app.post("/api/auth/login")
def login(email: str, password: str):
    user = db.query(User).filter(User.email == email).first()
    if not user or not user.verify_password(password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_token(user.id)
    return {"token": token, "user": {"id": user.id, "email": user.email, "name": user.name}}
```

**Frontend Login Page (`frontend/src/pages/LoginPage.js`)**

```javascript
export default function LoginPage({ onLogin }) {
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    const endpoint = isRegister ? "/api/auth/register" : "/api/auth/login";
    const body = isRegister 
      ? { email, password, name } 
      : { email, password };
    
    const res = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
    
    if (res.ok) {
      const data = await res.json();
      localStorage.setItem("token", data.token);
      localStorage.setItem("user", JSON.stringify(data.user));
      onLogin(data.user);
    }
  };

  return (
    <div style={S.loginContainer}>
      <h1>{isRegister ? "Create Account" : "Welcome Back"}</h1>
      <form onSubmit={handleSubmit}>
        {isRegister && (
          <input placeholder="Name" value={name} onChange={e => setName(e.target.value)} />
        )}
        <input 
          type="email" 
          placeholder="Email" 
          value={email} 
          onChange={e => setEmail(e.target.value)} 
        />
        <input 
          type="password" 
          placeholder="Password" 
          value={password} 
          onChange={e => setPassword(e.target.value)} 
        />
        <button type="submit">{isRegister ? "Sign Up" : "Login"}</button>
      </form>
      <p onClick={() => setIsRegister(!isRegister)}>
        {isRegister ? "Already have account? Login" : "Need account? Register"}
      </p>
    </div>
  );
}
```

---

## 4. Report Graphs (Sessions Per User)

### Overview
Displays visual graphs showing workout statistics, including total sessions, exercises performed, and progress over time.

### Implementation

**Frontend - Charts (`frontend/src/pages/ReportsPage.js`)**

```javascript
import { Bar, Line, Doughnut } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  ArcElement,
  Title,
  Tooltip,
  Legend
} from 'chart.js';

ChartJS.register(CategoryScale, LinearScale, BarElement, LineElement, PointElement, ArcElement, Title, Tooltip, Legend);

export default function ReportsPage({ user }) {
  const [chartData, setChartData] = useState(null);
  const [timeRange, setTimeRange] = useState('week'); // week, month, year

  useEffect(() => {
    fetch(`/api/reports/${user.id}?range=${timeRange}`, {
      headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
    })
      .then(res => res.json())
      .then(data => setChartData(data));
  }, [user.id, timeRange]);

  const sessionsChartData = {
    labels: chartData?.labels || [],
    datasets: [{
      label: 'Sessions Completed',
      data: chartData?.sessions || [],
      backgroundColor: 'rgba(75, 192, 192, 0.6)',
      borderColor: 'rgba(75, 192, 192, 1)',
      borderWidth: 2
    }]
  };

  const exerciseChartData = {
    labels: chartData?.exercises?.map(e => e.name) || [],
    datasets: [{
      data: chartData?.exercises?.map(e => e.count) || [],
      backgroundColor: ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF']
    }]
  };

  return (
    <div style={S.reportsPage}>
      <h1>Your Progress</h1>
      
      {/* Time Range Selector */}
      <div style={S.timeSelector}>
        <button onClick={() => setTimeRange('week')} className={timeRange === 'week' ? 'active' : ''}>Week</button>
        <button onClick={() => setTimeRange('month')} className={timeRange === 'month' ? 'active' : ''}>Month</button>
        <button onClick={() => setTimeRange('year')} className={timeRange === 'year' ? 'active' : ''}>Year</button>
      </div>

      {/* Sessions Over Time Chart */}
      <div style={S.chartCard}>
        <h2>Sessions Over Time</h2>
        <Line data={sessionsChartData} options={{ responsive: true }} />
      </div>

      {/* Exercise Distribution Chart */}
      <div style={S.chartRow}>
        <div style={S.chartCard}>
          <h2>Exercise Distribution</h2>
          <Doughnut data={exerciseChartData} options={{ responsive: true }} />
        </div>
        
        <div style={S.chartCard}>
          <h2>Total Stats</h2>
          <div style={S.statItems}>
            <div>Total Sessions: {chartData?.total_sessions}</div>
            <div>Total Reps: {chartData?.total_reps}</div>
            <div>Total Time: {chartData?.total_time} min</div>
            <div>Best Streak: {chartData?.best_streak} days</div>
          </div>
        </div>
      </div>
    </div>
  );
}
```

**Backend Reports API (`backend.py`)**

```python
@app.get("/api/reports/{user_id}")
def get_reports(user_id: int, range: str = "week", token: str = Header(...)):
    verify_token(token)
    
    # Determine date range
    today = datetime.now().date()
    if range == "week":
        start_date = today - timedelta(days=7)
    elif range == "month":
        start_date = today - timedelta(days=30)
    else:  # year
        start_date = today - timedelta(days=365)
    
    # Get sessions in range
    sessions = db.query(Session).filter(
        Session.user_id == user_id,
        Session.created_at >= start_date
    ).all()
    
    # Group by date for line chart
    date_counts = {}
    for session in sessions:
        date_str = session.created_at.strftime("%Y-%m-%d")
        date_counts[date_str] = date_counts.get(date_str, 0) + 1
    
    labels = sorted(date_counts.keys())
    session_counts = [date_counts[d] for d in labels]
    
    # Exercise distribution
    exercise_counts = {}
    for session in sessions:
        exercise_counts[session.exercise] = exercise_counts.get(session.exercise, 0) + 1
    
    exercises = [{"name": k, "count": v} for k, v in exercise_counts.items()]
    
    # Totals
    total_reps = sum(s.rep_count for s in sessions)
    total_time = sum(s.duration or 0 for s in sessions)
    
    return {
        "labels": labels,
        "sessions": session_counts,
        "exercises": exercises,
        "total_sessions": len(sessions),
        "total_reps": total_reps,
        "total_time": total_time,
        "best_streak": calculate_best_streak(user_id)
    }
```

---

## Database Schema

```python
# sessions table
class Session(Base):
    __tablename__ = "sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    exercise = Column(String)  # pushup, squat, lunges, plank
    rep_count = Column(Integer)  # or plank duration in seconds
    duration = Column(Integer, nullable=True)  # optional duration
    video_path = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
```

---

## Summary

| Feature | Technology | Key Files |
|---------|------------|-----------|
| Dashboard | React + FastAPI | DashboardPage.js, backend.py |
| Video Recording | MediaRecorder API + FastAPI | WorkoutPage.js, backend.py |
| User Login | JWT + SQLAlchemy | LoginPage.js, backend.py, models.py |
| Report Graphs | Chart.js + FastAPI | ReportsPage.js, backend.py |

All features use the existing WebSocket infrastructure for real-time workout tracking and can be integrated into the current application architecture.