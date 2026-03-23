import cv2
import time
import numpy as np
from src.utils import ang

# ── Thresholds ────────────────────────────────────────────────────────────────
PLANK_GOOD_MIN   = 165   # body line: perfect plank range min
PLANK_GOOD_MAX   = 185   # body line: perfect plank range max
PLANK_ACTIVE     = 158   # minimum body line to start timer
HIP_SAG_BAD      = 150   # below this: severely sagging
HEAD_OFFSET      = 40    # nose y vs shoulder y: head position
SHOULDER_WRIST_X = 50    # shoulder x vs wrist x: wrist placement
ELBOW_STRAIGHT   = 160   # elbow angle: high plank straight arms
ELBOW_BENT_MIN   = 80    # elbow angle: forearm plank
ELBOW_BENT_MAX   = 100   # elbow angle: forearm plank
SHOULDER_SYM_LIM = 25    # L/R shoulder y: body twist
HIP_SYM_LIM      = 20    # L/R hip y: hip rotation
NECK_ALIGN_LIM   = 35    # nose y vs shoulder: neck neutral

def process(image, idx, state):
    """
    Angles & checks:
    1.  Body line angle       shoulder→hip→ankle             [TIMER & MAIN]
    2.  Body line fallback    shoulder→hip→knee              [ANKLE HIDDEN]
    3.  Head position         nose y vs shoulder y           [HEAD DROP/UP]
    4.  Shoulder over wrist   shoulder x vs wrist x          [WRIST PLACEMENT]
    5.  Elbow angle           shoulder→elbow→wrist           [HIGH vs FOREARM]
    6.  Shoulder symmetry     L/R shoulder y                 [BODY TWIST]
    7.  Hip symmetry          L/R hip y                      [HIP ROTATION]
    8.  Neck alignment        nose vs shoulder neutral        [NECK STRAIN]
    9.  Hip sag severity      body_angle severity            [HOW BAD]
    10. Alignment percentage  body_angle interpolated        [FEEDBACK BAR]
    """
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

    # ── 1. BODY LINE ANGLE → timer ────────────────────────────────────────────
    body_angle = ang((shoulder, hip), (hip, ankle))
    align_pct  = float(np.clip(
        np.interp(body_angle, (120, 175), (0, 100)), 0, 100))
    cv2.putText(image, f"Body:{int(body_angle)}d",
                (hip[0]+8, hip[1]-10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,165,0), 2)

    # ── 9 & 10. BODY POSITION QUALITY ────────────────────────────────────────
    if body_angle >= PLANK_ACTIVE:
        if 'start_time' not in state:
            state['start_time'] = time.time()
        state['count'] = int(time.time() - state['start_time'])
        state['stage'] = f"{state['count']}s"

        if body_angle > PLANK_GOOD_MAX:
            feedbacks.append(("Hips too high!", "red"))
        elif body_angle < PLANK_GOOD_MIN:
            feedbacks.append(("Hips slightly low", "orange"))
        else:
            feedbacks.append(("Perfect plank alignment!", "green"))
    else:
        state.pop('start_time', None)
        state['stage'] = "HOLD"
        if body_angle < HIP_SAG_BAD:
            feedbacks.append(("Hips severely sagging!", "red"))
        else:
            feedbacks.append(("Raise hips to plank position!", "orange"))

    # ── 3. HEAD POSITION ─────────────────────────────────────────────────────
    if nose:
        head_diff = nose[1] - shoulder[1]
        if head_diff > HEAD_OFFSET:
            feedbacks.append(("Head dropping — look down!", "red"))
        elif head_diff < -HEAD_OFFSET:
            feedbacks.append(("Head too high — look down!", "orange"))
        else:
            feedbacks.append(("Head neutral: good", "green"))

        # ── 8. NECK ALIGNMENT ─────────────────────────────────────────────────
        neck_forward = abs(nose[0] - shoulder[0])
        if neck_forward > NECK_ALIGN_LIM:
            feedbacks.append(("Neck forward — tuck chin!", "orange"))

    # ── 4. SHOULDER OVER WRIST ───────────────────────────────────────────────
    if wrist:
        cv2.line(image, shoulder, wrist, (100,200,255), 1)
        sw_diff = abs(shoulder[0] - wrist[0])
        if sw_diff > SHOULDER_WRIST_X:
            feedbacks.append(("Wrists under shoulders!", "orange"))
        else:
            feedbacks.append(("Wrist placement: good", "green"))

    # ── 5. ELBOW ANGLE → high vs forearm plank ───────────────────────────────
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

    # ── 6. SHOULDER SYMMETRY → body twist ────────────────────────────────────
    if opp_s:
        if abs(shoulder[1] - opp_s[1]) > SHOULDER_SYM_LIM:
            feedbacks.append(("Body rotating — stay straight!", "orange"))

    # ── 7. HIP SYMMETRY → hip rotation ───────────────────────────────────────
    if opp_h:
        if abs(hip[1] - opp_h[1]) > HIP_SYM_LIM:
            feedbacks.append(("Keep hips level!", "orange"))

    return image, state, feedbacks[:7], align_pct