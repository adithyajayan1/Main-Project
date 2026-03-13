import time
import mediapipe as mp
from src.ThreadedCamera import ThreadedCamera
from src.exercies.Exercise import Exercise
from src.utils import *

mp_drawing = mp.solutions.drawing_utils
mp_holistic = mp.solutions.holistic
mp_pose = mp.solutions.pose

pose = mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5)
pose_landmark_drawing_spec = mp_drawing.DrawingSpec(thickness=5, circle_radius=2, color=(0, 0, 255))
pose_connection_drawing_spec = mp_drawing.DrawingSpec(thickness=1, circle_radius=1, color=(0, 255, 0))

# Shoulder tap detection (shoulder-elbow-wrist angle):
# Arm resting (plank position): elbow angle ~160-180 deg (arm straight, weight on hand)
# Arm raised to tap shoulder: elbow angle drops to ~60-100 deg (arm bends to touch shoulder)
# A tap is counted when arm goes from resting → raised (< TAP_DOWN) → back to resting (> TAP_UP)
TAP_DOWN = 100   # arm raised (tapping) when below this
TAP_UP   = 150   # arm back down (resting) when above this

# Body stability thresholds
HIP_TILT_LIMIT  = 35   # pixels: hips should stay level (front-facing)
SHOULDER_TILT_LIMIT = 30


def draw_panel(image, count, left_pct, right_pct, left_tapping, right_tapping, feedbacks):
    h = image.shape[0]
    overlay = image.copy()
    cv2.rectangle(overlay, (0, 0), (320, h), (20, 20, 20), -1)
    cv2.addWeighted(overlay, 0.55, image, 0.45, 0, image)

    cv2.putText(image, "GYMLYTICS", (10, 35), cv2.FONT_HERSHEY_DUPLEX, 0.9, (0, 200, 255), 2)
    cv2.putText(image, "Shoulder Taps", (10, 58), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (160, 160, 160), 1)
    cv2.line(image, (10, 68), (310, 68), (60, 60, 60), 1)

    cv2.putText(image, "TAPS", (10, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (160, 160, 160), 1)
    cv2.putText(image, str(count), (10, 160), cv2.FONT_HERSHEY_DUPLEX, 2.8, (0, 255, 150), 4)

    # Left arm indicator
    lc = (0, 210, 100) if left_tapping else (180, 180, 180)
    ls = "TAPPING" if left_tapping else "resting"
    cv2.putText(image, f"L arm: {ls} ({int(left_pct)}%)", (10, 190),
                cv2.FONT_HERSHEY_SIMPLEX, 0.48, lc, 1)
    cv2.rectangle(image, (10, 197), (310, 208), (60, 60, 60), -1)
    cv2.rectangle(image, (10, 197), (10 + int(left_pct * 3.0), 208), lc, -1)

    # Right arm indicator
    rc = (0, 210, 100) if right_tapping else (180, 180, 180)
    rs = "TAPPING" if right_tapping else "resting"
    cv2.putText(image, f"R arm: {rs} ({int(right_pct)}%)", (10, 225),
                cv2.FONT_HERSHEY_SIMPLEX, 0.48, rc, 1)
    cv2.rectangle(image, (10, 232), (310, 243), (60, 60, 60), -1)
    cv2.rectangle(image, (10, 232), (10 + int(right_pct * 3.0), 243), rc, -1)

    cv2.line(image, (10, 252), (310, 252), (60, 60, 60), 1)
    cv2.putText(image, "FEEDBACK", (10, 272), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (160, 160, 160), 1)
    for i, (msg, color) in enumerate(feedbacks[:6]):
        cv2.putText(image, msg, (10, 298 + i * 27), cv2.FONT_HERSHEY_SIMPLEX, 0.49, color, 1)
    cv2.putText(image, "ESC to quit", (10, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (100, 100, 100), 1)


class ShoulderTap(Exercise):
    def __init__(self):
        pass

    def exercise(self, source):
        threaded_camera = ThreadedCamera(source)
        time.sleep(1)

        count = 0
        frames = 0
        performedLeftTap = False
        performedRightTap = False
        ang1 = 180.0   # left arm:  shoulder(11)-elbow(13)-wrist(15)
        ang2 = 180.0   # right arm: shoulder(12)-elbow(14)-wrist(16)

        while True:
            _, image = threaded_camera.show_frame()
            if image is None:
                continue

            image = cv2.flip(image, 1)
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            results = pose.process(rgb)
            image.flags.writeable = True

            mp_drawing.draw_landmarks(image, results.pose_landmarks, mp_holistic.POSE_CONNECTIONS,
                                      landmark_drawing_spec=pose_landmark_drawing_spec,
                                      connection_drawing_spec=pose_connection_drawing_spec)

            idx = get_idx_to_coordinates(image, results)
            feedbacks = []
            frames += 1
            left_pct = 0.0
            right_pct = 0.0
            left_tapping = False
            right_tapping = False

            try:
                # ── LEFT ARM: shoulder(11)-elbow(13)-wrist(15) ──
                if 11 in idx and 13 in idx and 15 in idx:
                    sh_l, el_l, wr_l = idx[11], idx[13], idx[15]
                    cv2.line(image, sh_l, el_l, (255, 0, 0), 5)
                    cv2.line(image, el_l, wr_l, (255, 0, 0), 5)
                    cv2.circle(image, sh_l, 9, (0, 0, 255), cv2.FILLED)
                    cv2.circle(image, el_l, 9, (0, 0, 255), cv2.FILLED)
                    cv2.circle(image, wr_l, 9, (0, 0, 255), cv2.FILLED)
                    ang1 = ang((sh_l, el_l), (el_l, wr_l))
                    cv2.putText(image, f"{int(ang1)}d",
                                (el_l[0] - 40, el_l[1] - 15),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                    # Tap %: TAP_UP=0%, TAP_DOWN=100%
                    left_pct = float(np.clip(np.interp(ang1, (TAP_DOWN, TAP_UP), (100, 0)), 0, 100))
                    left_tapping = ang1 <= TAP_DOWN

                # ── RIGHT ARM: shoulder(12)-elbow(14)-wrist(16) ──
                if 12 in idx and 14 in idx and 16 in idx:
                    sh_r, el_r, wr_r = idx[12], idx[14], idx[16]
                    cv2.line(image, sh_r, el_r, (0, 0, 255), 5)
                    cv2.line(image, el_r, wr_r, (0, 0, 255), 5)
                    cv2.circle(image, sh_r, 9, (0, 0, 255), cv2.FILLED)
                    cv2.circle(image, el_r, 9, (0, 0, 255), cv2.FILLED)
                    cv2.circle(image, wr_r, 9, (0, 0, 255), cv2.FILLED)
                    ang2 = ang((sh_r, el_r), (el_r, wr_r))
                    cv2.putText(image, f"{int(ang2)}d",
                                (el_r[0] - 40, el_r[1] - 15),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                    right_pct = float(np.clip(np.interp(ang2, (TAP_DOWN, TAP_UP), (100, 0)), 0, 100))
                    right_tapping = ang2 <= TAP_DOWN

                # ── REP COUNTING ──
                # Left tap: arm bends (ang1 < TAP_DOWN) then extends back (ang1 > TAP_UP)
                if frames > 60:
                    if ang1 <= TAP_DOWN:
                        performedLeftTap = True
                    if ang1 >= TAP_UP and performedLeftTap:
                        count += 1
                        performedLeftTap = False

                    if ang2 <= TAP_DOWN:
                        performedRightTap = True
                    if ang2 >= TAP_UP and performedRightTap:
                        count += 1
                        performedRightTap = False

                # ── TAP FEEDBACK ──
                if left_tapping or right_tapping:
                    feedbacks.append(("Tap in progress!", (0, 210, 100)))
                else:
                    feedbacks.append(("Alternate arms", (180, 180, 180)))

                # ── BODY STABILITY: hips level ──
                if 23 in idx and 24 in idx:
                    hip_tilt = abs(idx[23][1] - idx[24][1])
                    if hip_tilt > HIP_TILT_LIMIT:
                        feedbacks.append(("Keep hips level!", (0, 80, 255)))
                    else:
                        feedbacks.append(("Hips stable: good", (0, 210, 100)))

                # ── BODY STABILITY: shoulders level ──
                if 11 in idx and 12 in idx:
                    sh_tilt = abs(idx[11][1] - idx[12][1])
                    if sh_tilt > SHOULDER_TILT_LIMIT:
                        feedbacks.append(("Keep shoulders level!", (0, 80, 255)))
                    else:
                        feedbacks.append(("Shoulders stable", (0, 210, 100)))

                # ── PLANK BASE CHECK: body line stable ──
                if 11 in idx and 23 in idx and 27 in idx:
                    body_ang = ang((idx[11], idx[23]), (idx[23], idx[27]))
                    if body_ang < 155:
                        feedbacks.append(("Hold plank base!", (0, 80, 255)))
                    else:
                        feedbacks.append(("Plank base: good", (0, 210, 100)))

            except Exception:
                feedbacks.append(("Adjust your position", (180, 180, 180)))

            if frames <= 60:
                feedbacks = [("Initializing... get into plank", (180, 180, 180))]

            if not feedbacks:
                feedbacks = [("Get into plank position", (180, 180, 180))]

            draw_panel(image, count, left_pct, right_pct, left_tapping, right_tapping, feedbacks)
            cv2.imshow('GymLytics - Shoulder Taps', rescale_frame(image, percent=100))
            if cv2.waitKey(5) & 0xFF == 27:
                break

        pose.close()
        cv2.destroyAllWindows()