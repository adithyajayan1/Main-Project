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

# Lunge knee angle (hip-knee-ankle):
# Standing UP:  front knee ~160-180 deg
# Proper DOWN:  front knee ~90 deg  (shin perpendicular to floor)
# Rep is counted: front knee goes below LUNGE_DOWN then returns above LUNGE_UP
LUNGE_DOWN = 110   # front knee below this = valid lunge depth
LUNGE_UP   = 155   # front knee above this = standing again

# Torso uprightness (shoulder-hip vertical): lean < 40px difference = good
TORSO_LEAN_LIMIT = 50


def draw_panel(image, count, stage, left_pct, right_pct, feedbacks):
    h = image.shape[0]
    overlay = image.copy()
    cv2.rectangle(overlay, (0, 0), (320, h), (20, 20, 20), -1)
    cv2.addWeighted(overlay, 0.55, image, 0.45, 0, image)

    cv2.putText(image, "GYMLYTICS", (10, 35), cv2.FONT_HERSHEY_DUPLEX, 0.9, (0, 200, 255), 2)
    cv2.putText(image, "Lunges", (10, 58), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (160, 160, 160), 1)
    cv2.line(image, (10, 68), (310, 68), (60, 60, 60), 1)

    cv2.putText(image, "REPS", (10, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (160, 160, 160), 1)
    cv2.putText(image, str(count), (10, 160), cv2.FONT_HERSHEY_DUPLEX, 2.8, (0, 255, 150), 4)

    sc = (0, 220, 100) if stage == "UP" else (0, 140, 255)
    cv2.putText(image, f"STAGE: {stage}", (10, 190), cv2.FONT_HERSHEY_SIMPLEX, 0.6, sc, 2)

    # Left leg depth bar
    lc = (0, 210, 100) if left_pct > 70 else (0, 165, 255) if left_pct > 40 else (0, 80, 255)
    cv2.putText(image, f"L knee: {int(left_pct)}%", (10, 215), cv2.FONT_HERSHEY_SIMPLEX, 0.48, lc, 1)
    cv2.rectangle(image, (10, 222), (310, 233), (60, 60, 60), -1)
    cv2.rectangle(image, (10, 222), (10 + int(left_pct * 3.0), 233), lc, -1)

    # Right leg depth bar
    rc = (0, 210, 100) if right_pct > 70 else (0, 165, 255) if right_pct > 40 else (0, 80, 255)
    cv2.putText(image, f"R knee: {int(right_pct)}%", (10, 250), cv2.FONT_HERSHEY_SIMPLEX, 0.48, rc, 1)
    cv2.rectangle(image, (10, 257), (310, 268), (60, 60, 60), -1)
    cv2.rectangle(image, (10, 257), (10 + int(right_pct * 3.0), 268), rc, -1)

    cv2.line(image, (10, 276), (310, 276), (60, 60, 60), 1)
    cv2.putText(image, "FEEDBACK", (10, 296), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (160, 160, 160), 1)
    for i, (msg, color) in enumerate(feedbacks[:6]):
        cv2.putText(image, msg, (10, 320 + i * 27), cv2.FONT_HERSHEY_SIMPLEX, 0.49, color, 1)
    cv2.putText(image, "ESC to quit", (10, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (100, 100, 100), 1)


class Lunges(Exercise):
    def __init__(self):
        pass

    def exercise(self, source):
        threaded_camera = ThreadedCamera(source)
        time.sleep(1)

        count = 0
        frames = 0
        performedLunge = False
        stage = "UP"
        ang1 = 180.0   # left knee: hip(23)-knee(25)-ankle(27)
        ang2 = 180.0   # right knee: hip(24)-knee(26)-ankle(28)

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

            try:
                # ── LEFT LEG: hip(23)-knee(25)-ankle(27) ──
                if 23 in idx and 25 in idx and 27 in idx:
                    hip_l, knee_l, ankle_l = idx[23], idx[25], idx[27]
                    cv2.line(image, hip_l, knee_l, (255, 0, 0), 5)
                    cv2.line(image, knee_l, ankle_l, (255, 0, 0), 5)
                    cv2.circle(image, hip_l, 9, (0, 0, 255), cv2.FILLED)
                    cv2.circle(image, knee_l, 9, (0, 0, 255), cv2.FILLED)
                    cv2.circle(image, ankle_l, 9, (0, 0, 255), cv2.FILLED)
                    ang1 = ang((hip_l, knee_l), (knee_l, ankle_l))
                    cv2.putText(image, f"{int(ang1)}d",
                                (knee_l[0] - 40, knee_l[1] - 15),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                    left_pct = float(np.clip(np.interp(ang1, (LUNGE_DOWN, LUNGE_UP), (100, 0)), 0, 100))

                # ── RIGHT LEG: hip(24)-knee(26)-ankle(28) ──
                if 24 in idx and 26 in idx and 28 in idx:
                    hip_r, knee_r, ankle_r = idx[24], idx[26], idx[28]
                    cv2.line(image, hip_r, knee_r, (0, 0, 255), 5)
                    cv2.line(image, knee_r, ankle_r, (0, 0, 255), 5)
                    cv2.circle(image, hip_r, 9, (0, 0, 255), cv2.FILLED)
                    cv2.circle(image, knee_r, 9, (0, 0, 255), cv2.FILLED)
                    cv2.circle(image, ankle_r, 9, (0, 0, 255), cv2.FILLED)
                    ang2 = ang((hip_r, knee_r), (knee_r, ankle_r))
                    cv2.putText(image, f"{int(ang2)}d",
                                (knee_r[0] - 40, knee_r[1] - 15),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                    right_pct = float(np.clip(np.interp(ang2, (LUNGE_DOWN, LUNGE_UP), (100, 0)), 0, 100))

                # ── REP COUNTING: track whichever knee bends most (front leg) ──
                # Front knee is the one with the smaller angle
                front_ang = min(ang1, ang2)

                if frames > 60:   # skip init frames
                    if front_ang <= LUNGE_DOWN:
                        performedLunge = True
                        stage = "DOWN"
                    if front_ang >= LUNGE_UP and performedLunge:
                        count += 1
                        performedLunge = False
                        stage = "UP"

                # ── DEPTH FEEDBACK ──
                if front_ang <= LUNGE_DOWN:
                    feedbacks.append(("Great lunge depth!", (0, 210, 100)))
                elif front_ang < 130:
                    feedbacks.append(("Go lower!", (0, 165, 255)))
                elif front_ang < LUNGE_UP:
                    feedbacks.append(("Lunge deeper", (0, 80, 255)))
                else:
                    feedbacks.append(("Ready, step forward", (180, 180, 180)))

                # ── BACK KNEE CHECK ──
                # Back knee (rear leg) should be close to floor: angle near 90 deg
                back_ang = max(ang1, ang2)
                if stage == "DOWN":
                    if back_ang > 120:
                        feedbacks.append(("Drop back knee lower!", (0, 165, 255)))
                    else:
                        feedbacks.append(("Back knee: good", (0, 210, 100)))

                # ── TORSO UPRIGHT CHECK ──
                if 11 in idx and 23 in idx:
                    sh = idx[11]
                    hp = idx[23]
                    lean = abs(sh[0] - hp[0])
                    if lean > TORSO_LEAN_LIMIT:
                        feedbacks.append(("Keep torso upright!", (0, 80, 255)))
                    else:
                        feedbacks.append(("Torso upright: good", (0, 210, 100)))
                elif 12 in idx and 24 in idx:
                    sh = idx[12]
                    hp = idx[24]
                    lean = abs(sh[0] - hp[0])
                    if lean > TORSO_LEAN_LIMIT:
                        feedbacks.append(("Keep torso upright!", (0, 80, 255)))
                    else:
                        feedbacks.append(("Torso upright: good", (0, 210, 100)))

                # ── FRONT KNEE ALIGNMENT ──
                # Front knee should track over front ankle, not cave inward
                if 25 in idx and 27 in idx:
                    kx, ax = idx[25][0], idx[27][0]
                    if abs(kx - ax) > 60:
                        feedbacks.append(("Knee over ankle!", (0, 165, 255)))

            except Exception:
                feedbacks.append(("Adjust your position", (180, 180, 180)))

            if frames <= 60:
                feedbacks = [("Initializing... hold still", (180, 180, 180))]

            if not feedbacks:
                feedbacks = [("Step forward to lunge", (180, 180, 180))]

            draw_panel(image, count, stage, left_pct, right_pct, feedbacks)
            cv2.imshow('GymLytics - Lunges', rescale_frame(image, percent=100))
            if cv2.waitKey(5) & 0xFF == 27:
                break

        pose.close()
        cv2.destroyAllWindows()