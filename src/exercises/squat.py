import cv2
import numpy as np
from src.utils import ang

# ── Thresholds ────────────────────────────────────────────────────────────────
KNEE_UP          = 160   # standing — knee almost straight
KNEE_DOWN        = 100   # valid squat depth — rep counted
TORSO_GOOD       = 65    # shoulder→hip→knee torso angle good
TORSO_WARN       = 45    # torso caving forward — warning
TORSO_LEAN_LIM   = 30    # excessive forward lean
KNEE_TOE_WARN    = 35    # knee x past ankle x (side) → knee over toe warn
KNEE_TOE_BAD     = 65    # knee x past ankle x (side) → bad
HIP_DROP_LIM     = 20    # L/R hip y diff → hip drop / lateral shift
KNEE_SYM_LIM     = 30    # L/R knee y diff → knee caving
ANKLE_LIFT_LIM   = 15    # ankle y movement → heel lifting
SHIN_ANGLE_MIN   = 65    # ankle→knee vs vertical: shin too vertical
SHIN_ANGLE_MAX   = 95    # ankle→knee vs vertical: shin too forward

def process(image, idx, state):
    feedbacks = []
    depth_pct = 0.0

    # ── Side selection ─────────────────────────────────────────────────────
    has_right = 24 in idx and 26 in idx and 28 in idx
    has_left  = 23 in idx and 25 in idx and 27 in idx

    if not has_right and not has_left:
        return image, state, [("No pose detected", "red"),
                               ("Face camera from the side", "gray")], 0.0

    if has_right:
        hip, knee, ankle = idx[24], idx[26], idx[28]
    else:
        hip, knee, ankle = idx[23], idx[25], idx[27]

    shoulder = idx.get(12) or idx.get(11)
    opp_hip  = idx.get(23) if has_right else idx.get(24)
    opp_knee = idx.get(25) if has_right else idx.get(26)

    is_form_valid = True
    knee_angle = ang((hip, knee), (knee, ankle))

    # ── 0. UPRIGHT INCLINATION ───────────────────────────────────────────────
    if shoulder:
        vertical_ref = (ankle[0], ankle[1] - 100)
        inclination = ang((shoulder, ankle), (ankle, vertical_ref))
        if inclination > 50:
            feedbacks.append(("Stand up straight!", "red"))
            is_form_valid = False

    # ── FORM CHECKS ──────────────────────────────────────────────────────────
    # TORSO ANGLE 
    if shoulder:
        torso_angle = ang((shoulder, hip), (hip, knee))
        cv2.putText(image, f"T:{int(torso_angle)}d",
                    (hip[0]+8, hip[1]-10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255,165,0), 1)
        if torso_angle < TORSO_LEAN_LIM:
            feedbacks.append(("Chest caving badly - stay upright!", "red"))
            is_form_valid = False
        elif torso_angle < TORSO_WARN:
            feedbacks.append(("Chest caving forward!", "orange"))

    # KNEE OVER TOE
    knee_toe_diff = knee[0] - ankle[0]
    if knee_toe_diff > KNEE_TOE_BAD:
        feedbacks.append(("Knees way over toes - sit back!", "red"))
        is_form_valid = False
    elif knee_toe_diff > KNEE_TOE_WARN:
        feedbacks.append(("Watch knee over toe", "orange"))

    # KNEE SYMMETRY -> caving
    if opp_knee:
        knee_diff = abs(knee[0] - opp_knee[0])
        if knee_diff < 30 and knee_angle < 130:
            feedbacks.append(("Knees caving in - push them out!", "red"))
            is_form_valid = False

    # BACK LEAN
    if shoulder:
        vertical_back = (hip[0], hip[1] - 100)
        back_lean = ang((shoulder, hip), (hip, vertical_back))
        if back_lean > 50:
            feedbacks.append(("Back leaning too far forward!", "red"))
            is_form_valid = False

    # HIP SYMMETRY
    if opp_hip:
        hip_diff = abs(hip[1] - opp_hip[1])
        if hip_diff > HIP_DROP_LIM:
            feedbacks.append(("Hips shifting sideways!", "orange"))

    # SHIN ANGLE
    vertical_ref2 = (ankle[0], ankle[1] - 100)
    shin_angle   = ang((knee, ankle), (ankle, vertical_ref2))
    if shin_angle < SHIN_ANGLE_MIN:
        feedbacks.append(("Shin too vertical — lean forward", "orange"))
    elif shin_angle > SHIN_ANGLE_MAX:
        feedbacks.append(("Too much forward shin lean", "orange"))

    # FOOT WIDTH
    if has_right and has_left:
        foot_width = abs(idx[28][0] - idx[27][0])
        if foot_width < 60:
            feedbacks.append(("Widen your stance", "orange"))
        elif foot_width > 250:
            feedbacks.append(("Stance too wide", "orange"))

    # ── 1. REP COUNTING ──────────────────────────────────────────────────────
    depth_pct  = float(np.clip(
        np.interp(knee_angle, (KNEE_DOWN, KNEE_UP), (100, 0)), 0, 100))
    cv2.putText(image, f"K:{int(knee_angle)}d",
                (knee[0]+8, knee[1]-10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,0), 2)

    if knee_angle <= KNEE_DOWN:
        state['stage'] = "DOWN"
        if is_form_valid:
            state['flag'] = True
            if hip[1] < knee[1]:
                feedbacks.append(("Below parallel: excellent!", "green"))
            else:
                feedbacks.append(("Great squat depth!", "green"))
        else:
            feedbacks.append(("Fix form to count rep!", "orange"))
    elif knee_angle < KNEE_UP:
        state['stage'] = "DOWN"
        if is_form_valid:
            feedbacks.append(("Go lower!", "orange"))
    else:
        if state.get('flag'):
            state['count'] += 1; state['flag'] = False
        state['stage'] = "UP"
        if is_form_valid:
            feedbacks.append(("Standing: ready", "green"))

    # Sort feedbacks to prioritize red > orange > green
    color_priority = {"red": 0, "orange": 1, "gray": 2, "green": 3}
    feedbacks.sort(key=lambda f: color_priority.get(f[1], 4))

    return image, state, feedbacks[:7], depth_pct