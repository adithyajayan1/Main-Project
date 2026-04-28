import cv2
import numpy as np
from src.utils import ang

# ── Thresholds ────────────────────────────────────────────────────────────────
LUNGE_DOWN       = 100   # front knee angle for valid lunge depth
LUNGE_UP         = 155   # standing — rep completed
BACK_KNEE_TARGET = 95    # back knee should approach 90° at bottom
BACK_KNEE_WARN   = 130   # back knee not bending enough
TORSO_LIM        = 50    # shoulder x vs hip x → torso lean
FRONT_KNEE_TOE   = 40    # front knee x vs front ankle x → knee over toe
HIP_LEVEL_LIM    = 35    # L/R hip y diff → hip drop
KNEE_ALIGN_LIM   = 30    # front knee x vs ankle x → valgus collapse
STRIDE_MIN       = 80    # min L/R ankle x distance → stride too short
STRIDE_MAX       = 300   # max L/R ankle x distance → stride too long
SHIN_VERTICAL    = 85    # front shin angle vs vertical

def process(image, idx, state):
    feedbacks = []
    depth_pct = 0.0

    has_left  = 23 in idx and 25 in idx and 27 in idx
    has_right = 24 in idx and 26 in idx and 28 in idx

    if not has_left and not has_right:
        return image, state, [("No pose detected", "red")], 0.0

    angles = []
    is_form_valid = True

    # ── Left leg ──────────────────────────────────────────────────────────────
    if has_left:
        lh, lk, la = idx[23], idx[25], idx[27]
        a_left = ang((lh, lk), (lk, la))
        angles.append(('left', a_left, lh, lk, la))

    # ── Right leg ─────────────────────────────────────────────────────────────
    if has_right:
        rh, rk, ra = idx[24], idx[26], idx[28]
        a_right = ang((rh, rk), (rk, ra))
        angles.append(('right', a_right, rh, rk, ra))

    if not angles:
        return image, state, [("Adjust position", "gray")], 0.0

    front = min(angles, key=lambda x: x[1])
    back  = max(angles, key=lambda x: x[1]) if len(angles) > 1 else None
    front_angle = front[1]
    fh, fk, fa  = front[2], front[3], front[4]

    shoulder = idx.get(11) or idx.get(12)
    hip_l    = idx.get(23)
    hip_r    = idx.get(24)
    hip_ref  = hip_l if hip_l else hip_r

    # ── 0. UPRIGHT INCLINATION ───────────────────────────────────────────────
    if shoulder and hip_ref:
        vertical_ref = (hip_ref[0], hip_ref[1] - 100)
        inclination = ang((shoulder, hip_ref), (hip_ref, vertical_ref))
        if inclination > 40:
            feedbacks.append(("Stand up straight!", "red"))
            is_form_valid = False

    # ── FORM CHECKS ──────────────────────────────────────────────────────────
    # TORSO UPRIGHTNESS
    if shoulder and hip_ref:
        torso_lean = abs(shoulder[0] - hip_ref[0])
        if torso_lean > TORSO_LIM:
            feedbacks.append(("Keep torso upright!", "red"))
            is_form_valid = False

    # FRONT KNEE OVER TOE
    knee_toe = fk[0] - fa[0]
    if knee_toe > FRONT_KNEE_TOE + 20:
        feedbacks.append(("Front knee way over toe - step further!", "red"))
        is_form_valid = False
    elif knee_toe > FRONT_KNEE_TOE:
        feedbacks.append(("Watch front knee", "orange"))

    # HIP LEVEL
    if hip_l and hip_r:
        hip_diff = abs(hip_l[1] - hip_r[1])
        if hip_diff > HIP_LEVEL_LIM:
            feedbacks.append(("Keep hips level!", "orange"))

    # STRIDE LENGTH
    if has_left and has_right:
        stride = abs(idx[27][0] - idx[28][0])
        if stride < STRIDE_MIN:
            feedbacks.append(("Stride too short!", "orange"))
        elif stride > STRIDE_MAX:
            feedbacks.append(("Stride too long!", "orange"))

    # FRONT SHIN ANGLE
    if front_angle < 140:
        vert = (fa[0], fa[1] - 100)
        shin_angle = ang((fk, fa), (fa, vert))
        if shin_angle > SHIN_VERTICAL + 15:
            feedbacks.append(("Front shin leaning too far", "orange"))

    # BACK KNEE ANGLE
    if back:
        back_angle = back[1]
        if front_angle < 130:  # only check mid-lunge
            if back_angle > BACK_KNEE_WARN:
                feedbacks.append(("Bend back knee more!", "orange"))
            elif back_angle < BACK_KNEE_TARGET + 10:
                pass # Good

    # ── 1. REP COUNTING ──────────────────────────────────────────────────────
    depth_pct = float(np.clip(
        np.interp(front_angle, (LUNGE_DOWN, LUNGE_UP), (100, 0)), 0, 100))

    if front_angle <= LUNGE_DOWN:
        state['stage'] = "DOWN"
        if is_form_valid:
            state['flag'] = True
            feedbacks.append(("Good lunge depth!", "green"))
        else:
            feedbacks.append(("Fix form to count rep!", "orange"))
    elif front_angle < LUNGE_UP:
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