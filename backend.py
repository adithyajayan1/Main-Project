import base64
import json
import traceback
from datetime import datetime, timedelta

import cv2
import mediapipe as mp
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, status, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from typing import Optional
from pydantic import BaseModel
import jwt

from src.utils import get_idx_to_coordinates

# ── Import models ────────────────────────────────────────────────
from models import SessionLocal, engine, User, Session

# ── Import exercise processors ────────────────────────────────────────────────
from src.exercises.pushup       import process as process_pushup
from src.exercises.squat        import process as process_squat
from src.exercises.lunges       import process as process_lunges
from src.exercises.plank        import process as process_plank

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── DB & Auth Setup ────────────────────────────────────────────────
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

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

class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str

class LoginRequest(BaseModel):
    email: str
    password: str

@app.post("/api/auth/register")
def register(req: RegisterRequest, db = Depends(get_db)):
    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(email=req.email, name=req.name)
    user.set_password(req.password)
    db.add(user)
    db.commit()
    token = create_token(user.id)
    return {"token": token, "user": {"id": user.id, "email": user.email, "name": user.name}}

@app.post("/api/auth/login")
def login(req: LoginRequest, db = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not user.verify_password(req.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_token(user.id)
    return {"token": token, "user": {"id": user.id, "email": user.email, "name": user.name}}

@app.get("/api/dashboard/{user_id}")
def get_dashboard(user_id: int, db = Depends(get_db)):
    user = db.query(User).get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    sessions = db.query(Session).filter(Session.user_id == user_id).order_by(Session.created_at.desc()).all()
    
    today = datetime.now().date()
    active_day_set = {s.created_at.date() for s in sessions}
    streak = 0
    # Start from today; fall back to yesterday if no session yet today
    check = today if today in active_day_set else today - timedelta(days=1)
    while check in active_day_set:
        streak += 1
        check -= timedelta(days=1)
    
    total_minutes = round(sum(s.duration or 0 for s in sessions) / 60, 1)
    
    recent = []
    for s in sessions[:5]:
        recent.append({
            "id": s.id, "exercise": s.exercise, "rep_count": s.rep_count,
            "duration": s.duration, "created_at": s.created_at.isoformat()
        })
        
    return {
        "stats": {
            "streak": streak,
            "total_workouts": len(sessions),
            "total_minutes": total_minutes,
            "this_week": len([s for s in sessions if (datetime.now() - s.created_at).days <= 7])
        },
        "recent_sessions": recent
    }


class SessionRequest(BaseModel):
    exercise: str
    rep_count: int
    duration: Optional[int] = None

@app.post("/api/sessions")
async def create_session(
    req: SessionRequest,
    authorization: str = Header(...),
    db = Depends(get_db)
):
    user_id = verify_token(authorization.replace("Bearer ", "").strip())

    session = Session(
        user_id=user_id, exercise=req.exercise, rep_count=req.rep_count,
        duration=req.duration, created_at=datetime.now()
    )
    db.add(session)
    db.commit()
    return {"session_id": session.id, "status": "saved"}

@app.get("/api/reports/{user_id}")
def get_reports(user_id: int, period: str = "week", authorization: str = Header(...), db = Depends(get_db)):
    token = authorization.replace("Bearer ", "").strip()
    verify_token(token)

    start_date = datetime.now()
    if period == "week":
        start_date = start_date - timedelta(days=7)
    elif period == "month":
        start_date = start_date - timedelta(days=30)
    else:
        start_date = start_date - timedelta(days=365)

    sessions = db.query(Session).filter(
        Session.user_id == user_id, Session.created_at >= start_date
    ).all()

    date_counts = {}
    for s in sessions:
        date_str = s.created_at.strftime("%Y-%m-%d")
        date_counts[date_str] = date_counts.get(date_str, 0) + 1

    # Fill every day in the range with 0 so the chart has no gaps
    num_days = 7 if period == "week" else (30 if period == "month" else 365)
    today = datetime.now().date()
    labels = [(today - timedelta(days=num_days - 1 - i)).strftime("%Y-%m-%d") for i in range(num_days)]
    session_counts = [date_counts.get(d, 0) for d in labels]

    exercise_counts = {}
    for s in sessions:
        exercise_counts[s.exercise] = exercise_counts.get(s.exercise, 0) + 1
    exercises = [{"name": k, "count": v} for k, v in exercise_counts.items()]

    total_reps = sum(s.rep_count for s in sessions)
    total_time = round(sum(s.duration or 0 for s in sessions) / 60, 1)

    # Best streak: longest consecutive days with at least one session (all-time, not range-limited)
    all_sessions = db.query(Session).filter(Session.user_id == user_id).all()
    active_days = sorted({s.created_at.date() for s in all_sessions}, reverse=True)
    best_streak = 0
    current_streak = 0
    prev_day = None
    for day in active_days:
        if prev_day is None or (prev_day - day).days == 1:
            current_streak += 1
            best_streak = max(best_streak, current_streak)
        else:
            current_streak = 1
        prev_day = day

    return {
        "labels": labels, "sessions": session_counts, "exercises": exercises,
        "total_sessions": len(sessions), "total_reps": total_reps, "total_time": total_time,
        "best_streak": best_streak
    }

# ── WebSocket ────────────────────────────────────────────────

mp_drawing = mp.solutions.drawing_utils
mp_holistic = mp.solutions.holistic
mp_pose    = mp.solutions.pose

pose_landmark_spec   = mp_drawing.DrawingSpec(thickness=5, circle_radius=2, color=(0,0,255))
pose_connection_spec = mp_drawing.DrawingSpec(thickness=1, circle_radius=1, color=(0,255,0))

EXERCISE_PROCESSORS = {
    "pushup":      process_pushup,
    "squat":       process_squat,
    "lunges":      process_lunges,
    "plank":       process_plank,
}

@app.websocket("/ws/{exercise_type}")
async def websocket_endpoint(websocket: WebSocket, exercise_type: str):
    await websocket.accept()

    pose      = mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5)
    state     = {"count": 0, "stage": "UP", "flag": False}
    processor = EXERCISE_PROCESSORS.get(exercise_type.lower())

    if not processor:
        await websocket.send_text(json.dumps({"error": f"Unknown exercise: {exercise_type}"}))
        await websocket.close()
        return

    try:
        while True:
            data    = await websocket.receive_text()
            payload = json.loads(data)

            if payload.get("type") == "reset":
                state = {"count": 0, "stage": "UP", "flag": False}
                continue

            img_data = base64.b64decode(payload["frame"].split(",")[1])
            np_arr   = np.frombuffer(img_data, np.uint8)
            image    = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

            if image is None:
                continue

            image = cv2.flip(image, 1)
            rgb   = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            results = pose.process(rgb)
            image.flags.writeable = True

            mp_drawing.draw_landmarks(
                image, results.pose_landmarks, mp_holistic.POSE_CONNECTIONS,
                landmark_drawing_spec=pose_landmark_spec,
                connection_drawing_spec=pose_connection_spec
            )

            idx       = get_idx_to_coordinates(image, results)
            feedbacks = []
            depth_pct = 0.0

            try:
                image, state, feedbacks, depth_pct = processor(image, idx, state)
            except Exception:
                traceback.print_exc()
                feedbacks = [("Adjust your position", "orange")]

            _, buffer = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 70])
            encoded   = base64.b64encode(buffer).decode('utf-8')

            await websocket.send_text(json.dumps({
                "frame":     f"data:image/jpeg;base64,{encoded}",
                "count":     state['count'],
                "stage":     state.get('stage', ''),
                "depth_pct": round(depth_pct, 1),
                "feedbacks": feedbacks,
            }))

    except WebSocketDisconnect:
        pass
    except Exception:
        traceback.print_exc()
    finally:
        pose.close()

@app.get("/")
def root():
    return {"status": "GymLytics backend running"}