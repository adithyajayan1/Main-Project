import cv2
import time
import numpy as np
from src.utils import ang

# ── Thresholds ────────────────────────────────────────────────────────────────
PLANK_GOOD_MIN   = 165   # body line: perfect plank range min
PLANK_GOOD_MAX   = 185   # body line: perfect plank range max
PLANK_ACTIVE     = 158   # minimum body line to start timer
GRACE_PERIOD     = 1.5   # seconds of bad form allowed before timer resets
HIP_SAG_BAD      = 150   # below this: severely sagging
HEAD_OFFSET      = 40    # nose y vs shoulder y: head position
SHOULDER_WRIST_X = 50    # shoulder x vs wrist x: wrist placement
ELBOW_STRAIGHT   = 160   # elbow angle: high plank straight arms
ELBOW_BENT_MIN   = 80    # elbow angle: forearm plank
ELBOW_BENT_MAX   = 100   # elbow angle: forearm plank
SHOULDER_SYM_LIM = 25    # L/R shoulder y: body twist
HIP_SYM_LIM      = 20    # L/R hip y: hip rotation
NECK_ALIGN_LIM   = 35    # nose y vs shoulder: neck neutral
MIN_ELEVATION    = 40    # ankle y must be > shoulder y by this much (shoulder elevated off floor)
MAX_HIP_DROP     = 60    # hip y must not be too far below shoulder y (catches shoulder-up, waist-on-floor)

def process(image, idx, state):
    feedbacks = []

    # ── Side selection ────────────────────────────────────────────────────────
    if 11 in idx and 23 in idx and 27 in idx:
        shoulder, hip, ankle = idx[11], idx[23], idx[27]
        opp_s = idx.get(12); opp_h = idx.get(24)
        elbow = idx.get(13); wrist = idx.get(15)
    elif 12 in idx and 24 in idx and 28 in idx:
        shoulder, hip, ankle = idx[12], idx[24], idx[28]
        opp_s = idx.get(11); opp_h = idx.get(23)
        elbow = idx.get(14); wrist = idx.get(16)
    else:
        # fallback with knee
        if 11 in idx and 23 in idx and 25 in idx:
            shoulder, hip, ankle = idx[11], idx[23], idx[25]
            opp_s = idx.get(12); opp_h = idx.get(24)
            elbow = idx.get(13); wrist = idx.get(15)
        elif 12 in idx and 24 in idx and 26 in idx:
            shoulder, hip, ankle = idx[12], idx[24], idx[26]
            opp_s = idx.get(11); opp_h = idx.get(23)
            elbow = idx.get(14); wrist = idx.get(16)
        else:
            return image, state, [("No pose detected", "red"),
                                   ("Face camera from the side", "gray")], 0.0

    nose = idx.get(0)

    # Draw body line
    cv2.line(image, shoulder, hip,    (255, 165, 0), 3)
    cv2.line(image, hip,      ankle,  (255, 165, 0), 3)
    cv2.circle(image, shoulder, 7, (0, 200, 255), cv2.FILLED)
    cv2.circle(image, hip,      7, (0, 200, 255), cv2.FILLED)
    cv2.circle(image, ankle,    7, (0, 200, 255), cv2.FILLED)

    is_form_valid = True

    # ── 0. HORIZONTAL INCLINATION ────────────────────────────────────────────
    vertical_ref = (ankle[0], ankle[1] - 100)
    inclination = ang((shoulder, ankle), (ankle, vertical_ref))
    if inclination < 50 or inclination > 130:
        feedbacks.append(("Get in horizontal position!", "red"))
        is_form_valid = False

    # ── 0b. ELEVATION CHECK (rejects lying flat or partial plank) ───────────
    # Shoulder must be elevated above ankle level (ankle_y > shoulder_y).
    elevation = ankle[1] - shoulder[1]
    if elevation < MIN_ELEVATION:
        feedbacks.append(("Get into plank position!", "red"))
        is_form_valid = False

    # Hip must stay close to shoulder height — catches shoulder-up, waist-on-floor.
    # In a real plank hip_y ≈ shoulder_y. If waist is on the floor, hip_y >> shoulder_y.
    hip_drop = hip[1] - shoulder[1]
    if hip_drop > MAX_HIP_DROP:
        feedbacks.append(("Raise your hips off the floor!", "red"))
        is_form_valid = False

    # ── FORM CHECKS ──────────────────────────────────────────────────────────
    body_angle = ang((shoulder, hip), (hip, ankle))
    
    if is_form_valid:
        if body_angle > PLANK_GOOD_MAX:
            feedbacks.append(("Hips too high - lower them!", "red"))
            is_form_valid = False
        elif body_angle < HIP_SAG_BAD:
            feedbacks.append(("Hips severely sagging - raise hips!", "red"))
            is_form_valid = False
        elif body_angle < PLANK_GOOD_MIN:
            feedbacks.append(("Hips slightly low", "orange"))

    # HEAD POSITION
    if nose:
        head_diff = nose[1] - shoulder[1]
        if head_diff > HEAD_OFFSET:
            feedbacks.append(("Head dropping — look down and forward!", "red"))
            is_form_valid = False
        elif head_diff < -HEAD_OFFSET:
            feedbacks.append(("Head too high — look down!", "orange"))

        # NECK ALIGNMENT
        neck_forward = abs(nose[0] - shoulder[0])
        if neck_forward > NECK_ALIGN_LIM:
            feedbacks.append(("Neck forward — tuck chin!", "orange"))

    # SHOULDER OVER WRIST
    if wrist:
        cv2.line(image, shoulder, wrist, (100,200,255), 1)
        sw_diff = abs(shoulder[0] - wrist[0])
        if sw_diff > SHOULDER_WRIST_X:
            feedbacks.append(("Keep wrists under shoulders!", "orange"))

    # ELBOW ANGLE
    if elbow and wrist:
        elbow_angle = ang((shoulder, elbow), (elbow, wrist))
        cv2.putText(image, f"El:{int(elbow_angle)}d",
                    (elbow[0]+5, elbow[1]-8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200,200,0), 1)
        if elbow_angle > ELBOW_STRAIGHT - 10:
            pass  # high plank — fine
        elif ELBOW_BENT_MIN <= elbow_angle <= ELBOW_BENT_MAX:
            pass  # forearm plank — fine
        else:
            feedbacks.append(("Check arm position!", "orange"))

    # SHOULDER SYMMETRY
    if opp_s:
        if abs(shoulder[1] - opp_s[1]) > SHOULDER_SYM_LIM:
            feedbacks.append(("Body twisting — stay straight!", "orange"))

    # HIP SYMMETRY
    if opp_h:
        if abs(hip[1] - opp_h[1]) > HIP_SYM_LIM:
            feedbacks.append(("Keep hips level!", "orange"))

    # ── 1. TIMER LOGIC ───────────────────────────────────────────────────────
    align_pct  = float(np.clip(
        np.interp(body_angle, (120, 175), (0, 100)), 0, 100))
    cv2.putText(image, f"Body:{int(body_angle)}d",
                (hip[0]+8, hip[1]-10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,165,0), 2)

    if body_angle >= PLANK_ACTIVE and is_form_valid:
        state.pop('bad_since', None)
        if 'start_time' not in state:
            state['start_time'] = time.time()
        state['count'] = int(time.time() - state['start_time'])
        state['stage'] = f"{state['count']}s"
        if not any(f[1] == "red" or f[1] == "orange" for f in feedbacks):
            feedbacks.append(("Perfect plank alignment!", "green"))
    else:
        now = time.time()
        if 'bad_since' not in state:
            state['bad_since'] = now
        elapsed_bad = now - state['bad_since']
        if elapsed_bad >= GRACE_PERIOD:
            state.pop('start_time', None)
            state.pop('bad_since', None)
        state['stage'] = "HOLD"
        feedbacks.append(("Fix form to start timer!", "orange"))

    color_priority = {"red": 0, "orange": 1, "gray": 2, "green": 3}
    feedbacks.sort(key=lambda f: color_priority.get(f[1], 4))

    return image, state, feedbacks[:7], align_pct