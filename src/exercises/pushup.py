import cv2
import numpy as np
from src.utils import ang

# ── Thresholds ────────────────────────────────────────────────────────────────
ELBOW_UP          = 155   # arms extended — UP stage
ELBOW_DOWN        = 95    # proper depth — rep counted
BODY_MIN          = 160   # shoulder→hip→ankle min (hips sagging)
BODY_MAX          = 195   # shoulder→hip→ankle max (hips too high)
ELBOW_FLARE_LIMIT = 80    # elbow→shoulder horizontal offset
HEAD_DROP_OFFSET  = 45    # nose y > shoulder y + this → head dropping
NECK_FORWARD_LIM  = 40    # nose x vs shoulder x
SHOULDER_SYM_LIM  = 25    # L/R shoulder y diff → body twist
WRIST_ALIGN_LIM   = 45    # wrist x vs shoulder x
HIP_SYM_LIM       = 25    # L/R hip y diff → hip rotation

def process(image, idx, state):
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

    is_form_valid = True
    ref_pt = ankle if ankle else knee

    # Require feet AND hip in frame — without them inclination/body checks are
    # blind and random arm movement (walking, gesturing) triggers false reps
    if not ref_pt:
        feedbacks.append(("Show full body — feet not visible!", "red"))
        is_form_valid = False
    if not hip:
        feedbacks.append(("Show full body — hips not visible!", "red"))
        is_form_valid = False

    # ── 0. HORIZONTAL INCLINATION ────────────────────────────────────────────
    if ref_pt:
        vertical_ref = (ref_pt[0], ref_pt[1] - 100)
        inclination = ang((shoulder, ref_pt), (ref_pt, vertical_ref))
        if inclination < 50 or inclination > 130:
            feedbacks.append(("Get in horizontal position!", "red"))
            is_form_valid = False

    # ── FORM CHECKS ──────────────────────────────────────────────────────────
    # BODY LINE
    if hip and ref_pt:
        cv2.line(image, shoulder, hip,    (255,165,0), 2)
        cv2.line(image, hip,      ref_pt, (255,165,0), 2)
        body_angle = ang((shoulder, hip), (hip, ref_pt))
        cv2.putText(image, f"B:{int(body_angle)}d",
                    (hip[0]+8, hip[1]-10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255,165,0), 1)
        if body_angle < BODY_MIN:
            feedbacks.append(("Hips sagging - keep body straight!", "red"))
            is_form_valid = False
        elif body_angle > BODY_MAX:
            feedbacks.append(("Hips too high - lower them!", "red"))
            is_form_valid = False

    # ELBOW FLARE
    elbow_angle = ang((shoulder, elbow), (elbow, wrist))
    if elbow_angle < 130:
        flare = abs(elbow[0] - shoulder[0])
        if flare > ELBOW_FLARE_LIMIT:
            feedbacks.append(("Tuck elbows closer to body!", "red"))
            is_form_valid = False

    # HEAD DROP
    if nose:
        if nose[1] > shoulder[1] + HEAD_DROP_OFFSET:
            feedbacks.append(("Head dropping - look slightly forward!", "red"))
            is_form_valid = False

        if abs(nose[0] - shoulder[0]) > NECK_FORWARD_LIM:
            feedbacks.append(("Head too far forward - tuck chin!", "orange"))

    # SHOULDERS / WRISTS / HIPS SYMMETRY
    if opp_s and abs(shoulder[1] - opp_s[1]) > SHOULDER_SYM_LIM:
        feedbacks.append(("Body twisting - stay level!", "orange"))

    if abs(wrist[0] - shoulder[0]) > WRIST_ALIGN_LIM:
        feedbacks.append(("Keep wrists directly under shoulders!", "orange"))

    if hip and opp_h and abs(hip[1] - opp_h[1]) > HIP_SYM_LIM:
        feedbacks.append(("Hips rotating - keep level!", "orange"))

    # ── 1. REP COUNTING ──────────────────────────────────────────────────────
    depth_pct   = float(np.clip(
        np.interp(elbow_angle, (ELBOW_DOWN, ELBOW_UP), (100, 0)), 0, 100))
    cv2.putText(image, f"E:{int(elbow_angle)}d",
                (elbow[0]+8, elbow[1]-10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,0), 2)

    going_down = elbow_angle < state.get('prev_elbow', elbow_angle + 1)
    state['prev_elbow'] = elbow_angle

    if elbow_angle <= ELBOW_DOWN:
        state['stage'] = "DOWN"
        if is_form_valid:
            state['flag'] = True
            feedbacks.append(("Great depth, push up!", "green"))
        else:
            state['flag'] = False  # bad form at bottom — don't count this rep
            feedbacks.append(("Fix form to count rep!", "orange"))
    elif elbow_angle < ELBOW_UP:
        if not is_form_valid:
            state['flag'] = False  # form broke mid-rep
        elif going_down and is_form_valid:
            state['stage'] = "DOWN"
            feedbacks.append(("Go lower!", "orange"))
    else:
        if state.get('flag') and is_form_valid:
            state['count'] += 1; state['flag'] = False
        elif state.get('flag') and not is_form_valid:
            state['flag'] = False  # reached top but form invalid — discard
        state['stage'] = "UP"
        if is_form_valid:
            feedbacks.append(("Arms extended: ready", "green"))

    # Sort feedbacks to prioritize red > orange > green
    color_priority = {"red": 0, "orange": 1, "gray": 2, "green": 3}
    feedbacks.sort(key=lambda f: color_priority.get(f[1], 4))

    return image, state, feedbacks[:7], depth_pct