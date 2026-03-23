import cv2
import numpy as np
from src.utils import ang

# ── Thresholds ────────────────────────────────────────────────────────────────
ELBOW_UP          = 155   # arms extended — UP stage
ELBOW_DOWN        = 90    # proper depth — rep counted
BODY_MIN          = 160   # shoulder→hip→ankle min (hips sagging)
BODY_MAX          = 195   # shoulder→hip→ankle max (hips too high)
ELBOW_FLARE_LIMIT = 80    # elbow→shoulder horizontal offset
HEAD_DROP_OFFSET  = 45    # nose y > shoulder y + this → head dropping
NECK_FORWARD_LIM  = 40    # nose x vs shoulder x
SHOULDER_SYM_LIM  = 25    # L/R shoulder y diff → body twist
WRIST_ALIGN_LIM   = 45    # wrist x vs shoulder x
HIP_SYM_LIM       = 25    # L/R hip y diff → hip rotation

def process(image, idx, state):
    """
    Angles & checks:
    1.  Elbow angle           shoulder→elbow→wrist           [REP COUNT]
    2.  Body line             shoulder→hip→ankle             [PLANK LINE]
    3.  Body line fallback    shoulder→hip→knee              [WHEN ANKLE HIDDEN]
    4.  Elbow flare           horizontal elbow vs shoulder   [ELBOW TUCK]
    5.  Head drop             nose y vs shoulder y           [HEAD DOWN]
    6.  Forward head          nose x vs shoulder x           [NECK FORWARD]
    7.  Shoulder symmetry     L vs R shoulder y              [BODY TWIST]
    8.  Wrist placement       wrist x vs shoulder x          [WRIST UNDER SHOULDER]
    9.  Hip symmetry          L vs R hip y                   [HIP ROTATION]
    10. Forearm vs horizontal elbow→wrist vs ground          [WRIST BEND]
    """
    feedbacks = []
    depth_pct = 0.0

    # ── Side selection ────────────────────────────────────────────────────────
    if 12 in idx and 14 in idx and 16 in idx:
        shoulder, elbow, wrist = idx[12], idx[14], idx[16]
        hip   = idx.get(24); ankle = idx.get(28); knee = idx.get(26)
        opp_s = idx.get(11); opp_h = idx.get(23); nose  = idx.get(0)
    elif 11 in idx and 13 in idx and 15 in idx:
        shoulder, elbow, wrist = idx[11], idx[13], idx[15]
        hip   = idx.get(23); ankle = idx.get(27); knee = idx.get(25)
        opp_s = idx.get(12); opp_h = idx.get(24); nose  = idx.get(0)
    else:
        return image, state, [("No pose detected", "red"),
                               ("Face camera from the side", "gray")], 0.0

    # Draw skeleton
    cv2.line(image, shoulder, elbow, (255, 0, 255), 4)
    cv2.line(image, elbow, wrist, (255, 0, 255), 4)
    cv2.circle(image, elbow,    8, (0, 255, 255), cv2.FILLED)
    cv2.circle(image, shoulder, 6, (0, 200, 255), cv2.FILLED)
    cv2.circle(image, wrist,    6, (0, 200, 255), cv2.FILLED)

    # ── 1. ELBOW ANGLE → rep counting ────────────────────────────────────────
    elbow_angle = ang((shoulder, elbow), (elbow, wrist))
    depth_pct   = float(np.clip(
        np.interp(elbow_angle, (ELBOW_DOWN, ELBOW_UP), (100, 0)), 0, 100))
    cv2.putText(image, f"E:{int(elbow_angle)}d",
                (elbow[0]+8, elbow[1]-10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,0), 2)

    if elbow_angle <= ELBOW_DOWN:
        state['stage'] = "DOWN"; state['flag'] = True
        feedbacks.append(("Great depth!", "green"))
    elif elbow_angle < ELBOW_UP:
        state['stage'] = "DOWN"
        feedbacks.append(("Go lower!", "orange"))
    else:
        if state.get('flag'):
            state['count'] += 1; state['flag'] = False
        state['stage'] = "UP"
        feedbacks.append(("Arms extended: ready", "green"))

    # ── 2 & 3. BODY LINE ─────────────────────────────────────────────────────
    ref_pt = ankle if ankle else knee
    if hip and ref_pt:
        cv2.line(image, shoulder, hip,    (255,165,0), 2)
        cv2.line(image, hip,      ref_pt, (255,165,0), 2)
        body_angle = ang((shoulder, hip), (hip, ref_pt))
        cv2.putText(image, f"B:{int(body_angle)}d",
                    (hip[0]+8, hip[1]-10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255,165,0), 1)
        if body_angle < BODY_MIN:
            feedbacks.append(("Hips sagging!", "red"))
        elif body_angle > BODY_MAX:
            feedbacks.append(("Hips too high!", "red"))
        else:
            feedbacks.append(("Body straight: good", "green"))
    else:
        feedbacks.append(("Show full body sideways", "gray"))

    # ── 4. ELBOW FLARE ───────────────────────────────────────────────────────
    if elbow_angle < 130:
        flare = abs(elbow[0] - shoulder[0])
        if flare > ELBOW_FLARE_LIMIT:
            feedbacks.append(("Tuck elbows in!", "red"))
        else:
            feedbacks.append(("Elbows tucked: good", "green"))

    # ── 5. HEAD DROP ─────────────────────────────────────────────────────────
    if nose:
        if nose[1] > shoulder[1] + HEAD_DROP_OFFSET:
            feedbacks.append(("Head dropping!", "red"))
        else:
            feedbacks.append(("Head neutral: good", "green"))

        # ── 6. FORWARD HEAD ──────────────────────────────────────────────────
        if abs(nose[0] - shoulder[0]) > NECK_FORWARD_LIM:
            feedbacks.append(("Head too far forward!", "orange"))

    # ── 7. SHOULDER SYMMETRY → body twist ────────────────────────────────────
    if opp_s:
        if abs(shoulder[1] - opp_s[1]) > SHOULDER_SYM_LIM:
            feedbacks.append(("Body rotating — stay straight!", "orange"))

    # ── 8. WRIST UNDER SHOULDER ───────────────────────────────────────────────
    if abs(wrist[0] - shoulder[0]) > WRIST_ALIGN_LIM:
        feedbacks.append(("Wrists under shoulders!", "orange"))

    # ── 9. HIP SYMMETRY → hip rotation ───────────────────────────────────────
    if hip and opp_h:
        if abs(hip[1] - opp_h[1]) > HIP_SYM_LIM:
            feedbacks.append(("Keep hips level!", "orange"))

    # ── 10. FOREARM vs HORIZONTAL → wrist bend ───────────────────────────────
    horiz = (wrist[0] + 80, wrist[1])
    forearm_angle = ang((elbow, wrist), (wrist, horiz))
    if forearm_angle < 65 or forearm_angle > 115:
        feedbacks.append(("Check wrist position!", "orange"))

    return image, state, feedbacks[:7], depth_pct