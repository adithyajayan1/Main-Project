import asyncio
import base64
import json
import traceback

import cv2
import mediapipe as mp
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from src.utils import get_idx_to_coordinates

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

            # Decode base64 frame from browser
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

            # Re-encode annotated frame
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