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
    """
    Angles & checks:
    1.  Front knee angle      hip→knee→ankle (front leg)     [REP COUNT]
    2.  Back knee angle       hip→knee→ankle (back leg)      [BACK KNEE BEND]
    3.  Torso uprightness     shoulder x vs hip x            [LEAN]
    4.  Front knee over toe   knee x vs ankle x              [KNEE TRACKING]
    5.  Hip level             L/R hip y diff                 [HIP DROP]
    6.  Stride length         L/R ankle x diff               [STRIDE WIDTH]
    7.  Front shin angle      ankle→knee vs vertical         [SHIN FORWARD]
    8.  Back shin angle       back ankle→knee vs vertical    [BACK LEG]
    9.  Knee valgus           front knee x vs ankle x        [COLLAPSE]
    10. Shoulder alignment    shoulder x vs hip x            [UPPER BODY]
    """
    feedbacks = []
    depth_pct = 0.0

    has_left  = 23 in idx and 25 in idx and 27 in idx
    has_right = 24 in idx and 26 in idx and 28 in idx

    if not has_left and not has_right:
        return image, state, [("No pose detected", "red")], 0.0

    angles = []

    # ── Left leg ──────────────────────────────────────────────────────────────
    if has_left:
        lh, lk, la = idx[23], idx[25], idx[27]
        cv2.line(image, lh, lk, (255, 0, 255), 4)
        cv2.line(image, lk, la, (255, 0, 255), 4)
        cv2.circle(image, lk, 8, (0, 255, 255), cv2.FILLED)
        a_left = ang((lh, lk), (lk, la))
        angles.append(('left', a_left, lh, lk, la))
        cv2.putText(image, f"L:{int(a_left)}d",
                    (lk[0]+8, lk[1]-10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,0), 2)

    # ── Right leg ─────────────────────────────────────────────────────────────
    if has_right:
        rh, rk, ra = idx[24], idx[26], idx[28]
        cv2.line(image, rh, rk, (0, 255, 255), 4)
        cv2.line(image, rk, ra, (0, 255, 255), 4)
        cv2.circle(image, rk, 8, (255, 0, 255), cv2.FILLED)
        a_right = ang((rh, rk), (rk, ra))
        angles.append(('right', a_right, rh, rk, ra))
        cv2.putText(image, f"R:{int(a_right)}d",
                    (rk[0]+8, rk[1]-10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,0), 2)

    if not angles:
        return image, state, [("Adjust position", "gray")], 0.0

    # ── 1. FRONT KNEE → rep counting ──────────────────────────────────────────
    # Front knee = whichever knee has SMALLER angle (more bent)
    front = min(angles, key=lambda x: x[1])
    back  = max(angles, key=lambda x: x[1]) if len(angles) > 1 else None
    front_angle = front[1]
    fh, fk, fa  = front[2], front[3], front[4]

    depth_pct = float(np.clip(
        np.interp(front_angle, (LUNGE_DOWN, LUNGE_UP), (100, 0)), 0, 100))

    if front_angle <= LUNGE_DOWN:
        state['stage'] = "DOWN"; state['flag'] = True
        feedbacks.append(("Good lunge depth!", "green"))
    elif front_angle < LUNGE_UP:
        state['stage'] = "DOWN"
        feedbacks.append(("Go lower!", "orange"))
    else:
        if state.get('flag'):
            state['count'] += 1; state['flag'] = False
        state['stage'] = "UP"
        feedbacks.append(("Standing: ready", "green"))

    # ── 2. BACK KNEE ANGLE ────────────────────────────────────────────────────
    if back:
        back_angle = back[1]
        bh, bk, ba = back[2], back[3], back[4]
        if front_angle < 130:  # only check mid-lunge
            if back_angle > BACK_KNEE_WARN:
                feedbacks.append(("Bend back knee more!", "orange"))
            elif back_angle < BACK_KNEE_TARGET + 10:
                feedbacks.append(("Back knee: good depth", "green"))

    # ── 3. TORSO UPRIGHTNESS ──────────────────────────────────────────────────
    shoulder = idx.get(11) or idx.get(12)
    hip_l    = idx.get(23)
    hip_r    = idx.get(24)
    hip_ref  = hip_l if hip_l else hip_r
    if shoulder and hip_ref:
        cv2.line(image, shoulder, hip_ref, (255,165,0), 2)
        torso_lean = abs(shoulder[0] - hip_ref[0])
        if torso_lean > TORSO_LIM:
            feedbacks.append(("Keep torso upright!", "orange"))
        else:
            feedbacks.append(("Torso upright: good", "green"))

    # ── 4. FRONT KNEE OVER TOE ────────────────────────────────────────────────
    knee_toe = fk[0] - fa[0]
    if knee_toe > FRONT_KNEE_TOE + 20:
        feedbacks.append(("Front knee way over toe!", "red"))
    elif knee_toe > FRONT_KNEE_TOE:
        feedbacks.append(("Watch front knee", "orange"))

    # ── 5. HIP LEVEL ──────────────────────────────────────────────────────────
    if hip_l and hip_r:
        hip_diff = abs(hip_l[1] - hip_r[1])
        if hip_diff > HIP_LEVEL_LIM:
            feedbacks.append(("Keep hips level!", "orange"))

    # ── 6. STRIDE LENGTH ──────────────────────────────────────────────────────
    if has_left and has_right:
        stride = abs(idx[27][0] - idx[28][0])
        if stride < STRIDE_MIN:
            feedbacks.append(("Stride too short!", "orange"))
        elif stride > STRIDE_MAX:
            feedbacks.append(("Stride too long!", "orange"))

    # ── 7. FRONT SHIN ANGLE vs VERTICAL ──────────────────────────────────────
    if front_angle < 140:
        vert = (fa[0], fa[1] - 100)
        shin_angle = ang((fk, fa), (fa, vert))
        if shin_angle > SHIN_VERTICAL + 15:
            feedbacks.append(("Front shin leaning too far", "orange"))

    # ── 8 & 9 handled by depth + knee tracking above ─────────────────────────

    return image, state, feedbacks[:7], depth_pct