import asyncio
import base64
import json
import time
import traceback

import cv2
import mediapipe as mp
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from src.utils import get_idx_to_coordinates, ang, rescale_frame

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
mp_pose = mp.solutions.pose

pose_landmark_drawing_spec = mp_drawing.DrawingSpec(thickness=5, circle_radius=2, color=(0, 0, 255))
pose_connection_drawing_spec = mp_drawing.DrawingSpec(thickness=1, circle_radius=1, color=(0, 255, 0))

# ── Thresholds ──────────────────────────────────────────────
PUSHUP   = dict(ELBOW_UP=155, ELBOW_DOWN=90,  BODY_MIN=160, BODY_MAX=195)
SQUAT    = dict(KNEE_UP=160,  KNEE_DOWN=110,  TORSO_GOOD=60, TORSO_WARN=40)
LUNGE    = dict(LUNGE_DOWN=110, LUNGE_UP=155)
PLANK    = dict(GOOD_MIN=165, GOOD_MAX=185,   ACTIVE=160)
SHOULDER = dict(TAP_DOWN=100, TAP_UP=150,     HIP_TILT=35, SHOULDER_TILT=30)


def process_pushup(image, idx, state):
    feedbacks = []
    depth_pct = 0.0
    T = PUSHUP

    if 12 in idx and 14 in idx and 16 in idx:
        shoulder, elbow, wrist = idx[12], idx[14], idx[16]
        hip, ankle = idx.get(24), idx.get(28)
    elif 11 in idx and 13 in idx and 15 in idx:
        shoulder, elbow, wrist = idx[11], idx[13], idx[15]
        hip, ankle = idx.get(23), idx.get(27)
    else:
        return image, state, [("No pose detected", "red"), ("Face camera from the side", "gray")], 0.0

    cv2.line(image, shoulder, elbow, (255, 0, 255), 4)
    cv2.line(image, elbow, wrist, (255, 0, 255), 4)
    cv2.circle(image, elbow, 8, (0, 255, 255), cv2.FILLED)

    elbow_angle = ang((shoulder, elbow), (elbow, wrist))
    depth_pct = float(np.clip(np.interp(elbow_angle, (T['ELBOW_DOWN'], T['ELBOW_UP']), (100, 0)), 0, 100))

    cv2.putText(image, f"Elbow:{int(elbow_angle)}d", (elbow[0] + 5, elbow[1] - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 0), 2)

    if elbow_angle <= T['ELBOW_DOWN']:
        state['stage'] = "DOWN"
        state['flag'] = True
        feedbacks.append(("Great depth!", "green"))
    elif elbow_angle < T['ELBOW_UP']:
        state['stage'] = "DOWN"
        feedbacks.append(("Go lower!", "orange"))
    else:
        if state.get('flag'):
            state['count'] += 1
            state['flag'] = False
        state['stage'] = "UP"
        feedbacks.append(("Arms extended: ready", "green"))

    knee_pt = idx.get(26) or idx.get(25)
    ref_pt = ankle if ankle else knee_pt
    if hip and ref_pt:
        body_angle = ang((shoulder, hip), (hip, ref_pt))
        if body_angle < T['BODY_MIN']:
            feedbacks.append(("Hips sagging!", "red"))
        elif body_angle > T['BODY_MAX']:
            feedbacks.append(("Hips too high!", "red"))
        else:
            feedbacks.append(("Body straight: good", "green"))

    if elbow_angle < 130:
        flare = abs(elbow[0] - shoulder[0])
        if flare > 80:
            feedbacks.append(("Tuck elbows in!", "red"))
        else:
            feedbacks.append(("Elbows: good", "green"))

    if 0 in idx:
        if idx[0][1] > shoulder[1] + 45:
            feedbacks.append(("Head dropping!", "red"))
        else:
            feedbacks.append(("Head neutral: good", "green"))

    return image, state, feedbacks, depth_pct


def process_squat(image, idx, state):
    feedbacks = []
    depth_pct = 0.0
    T = SQUAT

    if 24 in idx and 26 in idx and 28 in idx:
        hip, knee, ankle = idx[24], idx[26], idx[28]
        shoulder = idx.get(12)
    elif 23 in idx and 25 in idx and 27 in idx:
        hip, knee, ankle = idx[23], idx[25], idx[27]
        shoulder = idx.get(11)
    else:
        return image, state, [("No pose detected", "red"), ("Face camera from the side", "gray")], 0.0

    cv2.line(image, hip, knee, (255, 0, 255), 4)
    cv2.line(image, knee, ankle, (255, 0, 255), 4)
    cv2.circle(image, knee, 8, (0, 255, 255), cv2.FILLED)

    knee_angle = ang((hip, knee), (knee, ankle))
    depth_pct = float(np.clip(np.interp(knee_angle, (T['KNEE_DOWN'], T['KNEE_UP']), (100, 0)), 0, 100))

    cv2.putText(image, f"Knee:{int(knee_angle)}d", (knee[0] + 5, knee[1] - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 0), 2)

    if knee_angle <= T['KNEE_DOWN']:
        state['stage'] = "DOWN"
        state['flag'] = True
        feedbacks.append(("Good depth!", "green"))
    elif knee_angle < T['KNEE_UP']:
        state['stage'] = "DOWN"
        feedbacks.append(("Go lower!", "orange"))
    else:
        if state.get('flag'):
            state['count'] += 1
            state['flag'] = False
        state['stage'] = "UP"
        feedbacks.append(("Standing: ready", "green"))

    if shoulder:
        torso_angle = ang((shoulder, hip), (hip, knee))
        if torso_angle < T['TORSO_WARN']:
            feedbacks.append(("Chest caving!", "red"))
        elif torso_angle < T['TORSO_GOOD']:
            feedbacks.append(("Chest up more", "orange"))
        else:
            feedbacks.append(("Torso: good", "green"))

    return image, state, feedbacks, depth_pct


def process_lunge(image, idx, state):
    feedbacks = []
    depth_pct = 0.0
    T = LUNGE

    has_left  = 23 in idx and 25 in idx and 27 in idx
    has_right = 24 in idx and 26 in idx and 28 in idx

    if not has_left and not has_right:
        return image, state, [("No pose detected", "red")], 0.0

    angles = []
    if has_left:
        lh, lk, la = idx[23], idx[25], idx[27]
        a1 = ang((lh, lk), (lk, la))
        angles.append(a1)
        cv2.line(image, lh, lk, (255, 0, 255), 3)
        cv2.line(image, lk, la, (255, 0, 255), 3)
    if has_right:
        rh, rk, ra = idx[24], idx[26], idx[28]
        a2 = ang((rh, rk), (rk, ra))
        angles.append(a2)
        cv2.line(image, rh, rk, (0, 255, 255), 3)
        cv2.line(image, rk, ra, (0, 255, 255), 3)

    front_angle = min(angles)
    depth_pct = float(np.clip(np.interp(front_angle, (T['LUNGE_DOWN'], T['LUNGE_UP']), (100, 0)), 0, 100))

    if front_angle <= T['LUNGE_DOWN']:
        state['stage'] = "DOWN"
        state['flag'] = True
        feedbacks.append(("Good lunge depth!", "green"))
    elif front_angle < T['LUNGE_UP']:
        state['stage'] = "DOWN"
        feedbacks.append(("Go lower!", "orange"))
    else:
        if state.get('flag'):
            state['count'] += 1
            state['flag'] = False
        state['stage'] = "UP"
        feedbacks.append(("Standing: ready", "green"))

    return image, state, feedbacks, depth_pct


def process_plank(image, idx, state):
    feedbacks = []
    T = PLANK

    if 11 in idx and 23 in idx and 27 in idx:
        shoulder, hip, ankle = idx[11], idx[23], idx[27]
    elif 12 in idx and 24 in idx and 28 in idx:
        shoulder, hip, ankle = idx[12], idx[24], idx[28]
    else:
        return image, state, [("No pose detected", "red"), ("Face camera from the side", "gray")], 0.0

    cv2.line(image, shoulder, hip, (255, 165, 0), 3)
    cv2.line(image, hip, ankle, (255, 165, 0), 3)

    body_angle = ang((shoulder, hip), (hip, ankle))
    align_pct = float(np.clip(np.interp(body_angle, (120, 175), (0, 100)), 0, 100))

    if body_angle >= T['ACTIVE']:
        state['timer_running'] = True
        if 'start_time' not in state:
            state['start_time'] = time.time()
        state['count'] = int(time.time() - state['start_time'])
    else:
        state['timer_running'] = False
        state.pop('start_time', None)

    if body_angle > T['GOOD_MAX']:
        feedbacks.append(("Hips too high!", "red"))
    elif body_angle < T['GOOD_MIN'] and body_angle >= T['ACTIVE']:
        feedbacks.append(("Hips sagging slightly", "orange"))
    elif body_angle < T['ACTIVE']:
        feedbacks.append(("Hold plank position!", "red"))
    else:
        feedbacks.append(("Perfect plank!", "green"))

    state['stage'] = f"{state['count']}s"
    return image, state, feedbacks, align_pct


def process_shoulder_tap(image, idx, state):
    feedbacks = []
    T = SHOULDER

    has_left  = 11 in idx and 13 in idx and 15 in idx
    has_right = 12 in idx and 14 in idx and 16 in idx

    if not has_left and not has_right:
        return image, state, [("No pose detected", "red")], 0.0

    if has_left:
        ls, le, lw = idx[11], idx[13], idx[15]
        la = ang((ls, le), (le, lw))
        tapping_l = la < T['TAP_DOWN']
        if tapping_l and not state.get('left_tapping'):
            state['count'] += 1
        state['left_tapping'] = tapping_l
        cv2.line(image, ls, le, (255, 0, 255), 3)
        cv2.line(image, le, lw, (255, 0, 255), 3)

    if has_right:
        rs, re, rw = idx[12], idx[14], idx[16]
        ra = ang((rs, re), (re, rw))
        tapping_r = ra < T['TAP_DOWN']
        if tapping_r and not state.get('right_tapping'):
            state['count'] += 1
        state['right_tapping'] = tapping_r
        cv2.line(image, rs, re, (0, 255, 255), 3)
        cv2.line(image, re, rw, (0, 255, 255), 3)

    if has_left and has_right:
        hip_diff = abs(idx[23][1] - idx[24][1]) if 23 in idx and 24 in idx else 0
        if hip_diff > T['HIP_TILT']:
            feedbacks.append(("Keep hips level!", "red"))
        else:
            feedbacks.append(("Hips stable: good", "green"))

    tapping_any = state.get('left_tapping') or state.get('right_tapping')
    feedbacks.append(("Tapping!" if tapping_any else "In plank position", "green" if tapping_any else "gray"))
    state['stage'] = "TAP" if tapping_any else "HOLD"

    return image, state, feedbacks, 0.0


EXERCISE_PROCESSORS = {
    "pushup":      process_pushup,
    "squat":       process_squat,
    "lunges":      process_lunge,
    "plank":       process_plank,
    "shouldertap": process_shoulder_tap,
}


@app.websocket("/ws/{exercise_type}")
async def websocket_endpoint(websocket: WebSocket, exercise_type: str):
    await websocket.accept()

    pose = mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5)
    state = {"count": 0, "stage": "UP", "flag": False}
    processor = EXERCISE_PROCESSORS.get(exercise_type.lower())

    if not processor:
        await websocket.send_text(json.dumps({"error": f"Unknown exercise: {exercise_type}"}))
        await websocket.close()
        return

    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)

            if payload.get("type") == "reset":
                state = {"count": 0, "stage": "UP", "flag": False}
                continue

            # Decode base64 frame from browser
            img_data = base64.b64decode(payload["frame"].split(",")[1])
            np_arr = np.frombuffer(img_data, np.uint8)
            image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

            if image is None:
                continue

            image = cv2.flip(image, 1)
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            results = pose.process(rgb)
            image.flags.writeable = True

            mp_drawing.draw_landmarks(
                image, results.pose_landmarks, mp_holistic.POSE_CONNECTIONS,
                landmark_drawing_spec=pose_landmark_drawing_spec,
                connection_drawing_spec=pose_connection_drawing_spec
            )

            idx = get_idx_to_coordinates(image, results)
            feedbacks = []
            depth_pct = 0.0

            try:
                image, state, feedbacks, depth_pct = processor(image, idx, state)
            except Exception:
                feedbacks = [("Adjust your position", "orange")]

            # Encode processed frame back to base64
            _, buffer = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 70])
            encoded = base64.b64encode(buffer).decode('utf-8')

            response = {
                "frame": f"data:image/jpeg;base64,{encoded}",
                "count": state['count'],
                "stage": state.get('stage', ''),
                "depth_pct": round(depth_pct, 1),
                "feedbacks": feedbacks,
            }

            await websocket.send_text(json.dumps(response))

    except WebSocketDisconnect:
        pass
    except Exception:
        traceback.print_exc()
    finally:
        pose.close()


@app.get("/")
def root():
    return {"status": "GymLytics backend running"}