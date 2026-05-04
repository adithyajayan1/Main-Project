import cv2
import numpy as np
from src.utils import ang

# ── Thresholds ────────────────────────────────────────────────────────────────
KNEE_UP          = 168   # standing — knee almost straight (raised for noise margin)
KNEE_DOWN        = 100  # valid squat depth — rep counted
KNEE_ACTIVE      = 120   # knee bent enough that form checks are meaningful
TORSO_GOOD       = 65    # shoulder→hip→knee torso angle good
TORSO_WARN       = 45    # torso caving forward — warning
TORSO_LEAN_LIM   = 30    # excessive forward lean
KNEE_TOE_WARN    = 35    # knee x past ankle x (side) → knee over toe warn
KNEE_TOE_BAD     = 65    # knee x past ankle x (side) → bad
HIP_DROP_LIM     = 20    # L/R hip y diff → hip drop / lateral shift
KNEE_SYM_LIM     = 30    # L/R knee y diff → knee caving
ANKLE_LIFT_LIM   = 15    # ankle y movement → heel lifting
SHIN_ANGLE_MIN   = 10    # ankle→knee vs vertical: shin too vertical
SHIN_ANGLE_MAX   = 50    # ankle→knee vs vertical: shin too forward
MIN_HOLD_FRAMES  = 3     # frames at depth before rep is flagged (noise filter)

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

    # Draw skeleton
    cv2.line(image, hip, knee,   (255, 0, 255), 4)
    cv2.line(image, knee, ankle, (255, 0, 255), 4)
    cv2.circle(image, knee,  8, (0, 255, 255), cv2.FILLED)
    cv2.circle(image, hip,   6, (0, 200, 255), cv2.FILLED)
    cv2.circle(image, ankle, 6, (0, 200, 255), cv2.FILLED)
    if shoulder:
        cv2.line(image, shoulder, hip, (255, 165, 0), 2)

    is_form_valid = True
    knee_angle = ang((hip, knee), (knee, ankle))
    is_in_squat = knee_angle < KNEE_ACTIVE   # knee bent enough for form checks

    # ── 0. UPRIGHT INCLINATION ───────────────────────────────────────────────
    # Only check posture when NOT actively squatting (standing phase)
    if shoulder and not is_in_squat:
        vertical_ref = (ankle[0], ankle[1] - 100)
        inclination = ang((shoulder, ankle), (ankle, vertical_ref))
        if inclination > 50:
            feedbacks.append(("Stand up straight!", "red"))
            is_form_valid = False

    # ── FORM CHECKS (only when actively squatting) ───────────────────────────
    if is_in_squat:
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

        # KNEE OVER TOE (abs for side-agnostic)
        knee_toe_diff = abs(knee[0] - ankle[0])
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

        # SHIN ANGLE (only meaningful during squat)
        vertical_ref2 = (ankle[0], ankle[1] - 100)
        shin_angle   = ang((knee, ankle), (ankle, vertical_ref2))
        if shin_angle < SHIN_ANGLE_MIN:
            feedbacks.append(("Shin too vertical — lean forward", "orange"))
        elif shin_angle > SHIN_ANGLE_MAX:
            feedbacks.append(("Too much forward shin lean", "orange"))

    # ── 1. REP COUNTING ──────────────────────────────────────────────────────
    depth_pct  = float(np.clip(
        np.interp(knee_angle, (KNEE_DOWN, KNEE_UP), (100, 0)), 0, 100))
    cv2.putText(image, f"K:{int(knee_angle)}d",
                (knee[0]+8, knee[1]-10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,0), 2)

    # Initialize hold counter if missing
    if 'hold_frames' not in state:
        state['hold_frames'] = 0

    if knee_angle <= KNEE_DOWN:
        state['stage'] = "DOWN"
        state['hold_frames'] += 1
        if is_form_valid and state['hold_frames'] >= MIN_HOLD_FRAMES:
            state['flag'] = True
            if hip[1] > knee[1]:
                feedbacks.append(("Below parallel: excellent!", "green"))
            else:
                feedbacks.append(("Great squat depth!", "green"))
        elif not is_form_valid:
            feedbacks.append(("Fix form to count rep!", "orange"))
        else:
            feedbacks.append(("Hold depth...", "green"))
    elif knee_angle < KNEE_UP:
        state['stage'] = "DOWN"
        state['hold_frames'] = 0   # reset — not at full depth
        if is_form_valid:
            feedbacks.append(("Go lower!", "red"))
    else:
        # Fully standing — count rep if flagged from valid deep squat
        if state.get('flag'):
            state['count'] += 1
            state['flag'] = False
        state['stage'] = "UP"
        state['hold_frames'] = 0
        if is_form_valid:
            feedbacks.append(("Standing: ready", "green"))

    # Sort feedbacks to prioritize red > orange > green
    color_priority = {"red": 0, "orange": 1, "gray": 2, "green": 3}
    feedbacks.sort(key=lambda f: color_priority.get(f[1], 4))

    return image, state, feedbacks[:7], depth_pct