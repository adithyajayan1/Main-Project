import base64
import json
import os
import subprocess
import tempfile
import traceback
from datetime import datetime, timedelta

import cv2
import mediapipe as mp
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, UploadFile, File, Form, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
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

def create_token(user_id: int) -> str:
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(days=7)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str) -> int:
    try:
        payload = jwt.decode(token.replace("Bearer ", ""), SECRET_KEY, algorithms=[ALGORITHM])
        return payload["user_id"]
    except Exception:
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
def get_dashboard(user_id: int, authorization: str = Header(...), db = Depends(get_db)):
    verify_token(authorization)
    user = db.query(User).get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    sessions = db.query(Session).filter(Session.user_id == user_id).order_by(Session.created_at.desc()).all()

    # Real consecutive-day streak
    streak = 0
    if sessions:
        today = datetime.now().date()
        seen_days = sorted({s.created_at.date() for s in sessions}, reverse=True)
        expected = today
        for day in seen_days:
            if day == expected or day == today:
                streak += 1
                expected = day - timedelta(days=1)
            else:
                break
    
    total_seconds = sum(s.duration or 0 for s in sessions)
    total_minutes = total_seconds // 60
    
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

@app.post("/api/sessions")
async def create_session(
    video: UploadFile = File(...),
    exercise: str = Form(...),
    rep_count: int = Form(...),
    duration: Optional[int] = Form(None),
    authorization: str = Header(...),
    db = Depends(get_db)
):
    user_id = verify_token(authorization)

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    webm_tmp = os.path.join(tempfile.gettempdir(), f"session_{timestamp}.webm")
    mp4_tmp  = os.path.join(tempfile.gettempdir(), f"session_{timestamp}.mp4")

    with open(webm_tmp, "wb") as f:
        f.write(await video.read())

    result = subprocess.run(
        ["ffmpeg", "-y", "-i", webm_tmp, "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-c:a", "aac", mp4_tmp],
        capture_output=True
    )
    os.unlink(webm_tmp)
    if result.returncode != 0:
        raise HTTPException(status_code=500, detail="Video conversion failed")

    session = Session(
        user_id=user_id, exercise=exercise, rep_count=rep_count,
        duration=duration, video_path=mp4_tmp, created_at=datetime.now()
    )
    db.add(session)
    db.commit()
    return {"session_id": session.id, "status": "saved"}

@app.post("/api/convert")
async def convert_video(video: UploadFile = File(...)):
    """Convert an uploaded WebM to MP4 without requiring auth — for guest users."""
    webm_tmp = os.path.join(tempfile.gettempdir(), f"upload_{datetime.now().strftime('%Y%m%d%H%M%S%f')}.webm")
    mp4_tmp  = webm_tmp.replace(".webm", ".mp4")

    with open(webm_tmp, "wb") as f:
        f.write(await video.read())

    result = subprocess.run(
        ["ffmpeg", "-y", "-i", webm_tmp, "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-c:a", "aac", mp4_tmp],
        capture_output=True
    )
    os.unlink(webm_tmp)
    if result.returncode != 0:
        raise HTTPException(status_code=500, detail="Video conversion failed")

    filename = f"workout_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
    return FileResponse(mp4_tmp, media_type="video/mp4", filename=filename, background=None)

@app.get("/api/sessions/{session_id}/download")
def download_session(session_id: int, authorization: str = Header(...), db = Depends(get_db)):
    requesting_user_id = verify_token(authorization)

    session = db.query(Session).filter(Session.id == session_id).first()
    if not session or not session.video_path:
        raise HTTPException(status_code=404, detail="Session or video not found")

    if session.user_id != requesting_user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    if not os.path.exists(session.video_path):
        raise HTTPException(status_code=404, detail="Video file not found on disk")

    filename = f"{session.exercise}_{session.rep_count}reps.mp4"
    return FileResponse(session.video_path, media_type="video/mp4", filename=filename)

@app.get("/api/reports/{user_id}")
def get_reports(user_id: int, range: str = "week", authorization: str = Header(...), db = Depends(get_db)):
    verify_token(authorization)

    start_date = datetime.now()
    if range == "week":
        start_date = start_date - timedelta(days=7)
    elif range == "month":
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
        
    labels = sorted(date_counts.keys())
    session_counts = [date_counts[d] for d in labels]
    
    exercise_counts = {}
    for s in sessions:
        exercise_counts[s.exercise] = exercise_counts.get(s.exercise, 0) + 1
    exercises = [{"name": k, "count": v} for k, v in exercise_counts.items()]
    
    total_reps = sum(s.rep_count for s in sessions)
    total_secs = sum(s.duration or 0 for s in sessions)
    total_time = total_secs // 60
    
    return {
        "labels": labels, "sessions": session_counts, "exercises": exercises,
        "total_sessions": len(sessions), "total_reps": total_reps,
        "total_time": total_time, "total_secs": total_secs,
        "best_streak": 0
    }

# ── WebSocket ────────────────────────────────────────────────

mp_drawing = mp.solutions.drawing_utils
mp_holistic = mp.solutions.holistic
mp_pose     = mp.solutions.pose

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

            idx       = get_idx_to_coordinates(image, results)
            feedbacks = []
            depth_pct = 0.0

            try:
                image, state, feedbacks, depth_pct = processor(image, idx, state)
            except Exception:
                traceback.print_exc()
                feedbacks = [("Adjust your position", "orange")]

            # Draw all 33 landmarks — red if bad form, green if good
            has_bad = any(f[1] == "red" for f in feedbacks)
            skel_bgr = (0, 0, 255) if has_bad else (0, 220, 0)
            lm_spec   = mp_drawing.DrawingSpec(thickness=4, circle_radius=3, color=skel_bgr)
            conn_spec = mp_drawing.DrawingSpec(thickness=2, circle_radius=1, color=skel_bgr)
            mp_drawing.draw_landmarks(
                image, results.pose_landmarks, mp_holistic.POSE_CONNECTIONS,
                landmark_drawing_spec=lm_spec,
                connection_drawing_spec=conn_spec
            )

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