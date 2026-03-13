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

# Knee angle thresholds (hip-knee-ankle, side view)
# Standing UP:  knee angle ~160-180 deg
# Parallel DOWN: knee angle ~90 deg (thighs parallel to floor)
KNEE_UP   = 160   # above = standing, rep completed
KNEE_DOWN = 110   # below = counted as valid squat depth

# Torso angle (shoulder-hip-knee)
# Proper: chest up, angle > 60 deg
# Improper: hunching forward, angle < 40 deg
TORSO_GOOD = 60
TORSO_WARN = 40

# Knee-over-toe: horizontal distance knee vs ankle (pixels, side view)
KNEE_TOE_WARN  = 40
KNEE_TOE_BAD   = 70


def draw_panel(image, count, stage, depth_pct, feedbacks):
    h = image.shape[0]
    overlay = image.copy()
    cv2.rectangle(overlay, (0, 0), (320, h), (20, 20, 20), -1)
    cv2.addWeighted(overlay, 0.55, image, 0.45, 0, image)

    cv2.putText(image, "GYMLYTICS", (10, 35), cv2.FONT_HERSHEY_DUPLEX, 0.9, (0, 200, 255), 2)
    cv2.putText(image, "Squat", (10, 58), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (160, 160, 160), 1)
    cv2.line(image, (10, 68), (310, 68), (60, 60, 60), 1)

    cv2.putText(image, "REPS", (10, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (160, 160, 160), 1)
    cv2.putText(image, str(count), (10, 160), cv2.FONT_HERSHEY_DUPLEX, 2.8, (0, 255, 150), 4)

    sc = (0, 220, 100) if stage == "UP" else (0, 140, 255)
    cv2.putText(image, f"STAGE: {stage}", (10, 190), cv2.FONT_HERSHEY_SIMPLEX, 0.6, sc, 2)

    bc = (0, 210, 100) if depth_pct > 70 else (0, 165, 255) if depth_pct > 40 else (0, 80, 255)
    cv2.putText(image, f"Depth: {int(depth_pct)}%", (10, 215), cv2.FONT_HERSHEY_SIMPLEX, 0.5, bc, 1)
    cv2.rectangle(image, (10, 222), (310, 235), (60, 60, 60), -1)
    cv2.rectangle(image, (10, 222), (10 + int(depth_pct * 3.0), 235), bc, -1)

    cv2.line(image, (10, 244), (310, 244), (60, 60, 60), 1)
    cv2.putText(image, "FEEDBACK", (10, 264), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (160, 160, 160), 1)
    for i, (msg, color) in enumerate(feedbacks[:7]):
        cv2.putText(image, msg, (10, 290 + i * 27), cv2.FONT_HERSHEY_SIMPLEX, 0.49, color, 1)
    cv2.putText(image, "ESC to quit", (10, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (100, 100, 100), 1)


class Squat(Exercise):
    def __init__(self):
        pass

    def exercise(self, source):
        threaded_camera = ThreadedCamera(source)
        time.sleep(1)

        scount = 0
        performedSquat = False
        stage = "UP"
        depth_pct = 0.0

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
            depth_pct = 0.0

            try:
                # Side view — prefer right side (24=hip, 26=knee, 28=ankle)
                # fallback left (23, 25, 27)
                if 24 in idx and 26 in idx and 28 in idx:
                    hip, knee, ankle = idx[24], idx[26], idx[28]
                    shoulder = idx.get(12)
                elif 23 in idx and 25 in idx and 27 in idx:
                    hip, knee, ankle = idx[23], idx[25], idx[27]
                    shoulder = idx.get(11)
                else:
                    feedbacks = [("No lower body detected", (0, 80, 255)),
                                 ("Stand sideways to camera", (180, 180, 180))]
                    draw_panel(image, scount, stage, depth_pct, feedbacks)
                    cv2.imshow('GymLytics - Squat', rescale_frame(image, percent=100))
                    if cv2.waitKey(5) & 0xFF == 27:
                        break
                    continue

                # Draw leg skeleton
                cv2.line(image, hip, knee, (0, 0, 255), 4)
                cv2.line(image, knee, ankle, (0, 0, 255), 4)
                cv2.circle(image, hip, 8, (0, 255, 255), cv2.FILLED)
                cv2.circle(image, knee, 8, (0, 255, 255), cv2.FILLED)
                cv2.circle(image, ankle, 8, (0, 255, 255), cv2.FILLED)

                # ── 1. KNEE ANGLE (hip-knee-ankle) → rep counting ──
                knee_angle = ang((hip, knee), (knee, ankle))
                cv2.putText(image, f"Knee:{int(knee_angle)}d", (knee[0] + 5, knee[1] - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)

                # Depth %: KNEE_UP=0%, KNEE_DOWN=100%
                depth_pct = float(np.clip(np.interp(knee_angle, (KNEE_DOWN, KNEE_UP), (100, 0)), 0, 100))

                try:
                    l1 = np.linspace(hip, knee, 100)
                    l2 = np.linspace(knee, ankle, 100)
                    center, radius, sa, ea = convert_arc(l1[90], l2[10], sagitta=15)
                    draw_ellipse(image, center, (radius, radius), -1, sa, ea, 255)
                except Exception:
                    pass

                if knee_angle <= KNEE_DOWN:
                    stage = "DOWN"
                    performedSquat = True
                    feedbacks.append(("Great squat depth!", (0, 210, 100)))
                elif knee_angle < KNEE_UP:
                    stage = "DOWN"
                    feedbacks.append(("Go lower!", (0, 165, 255)))
                else:
                    if performedSquat:
                        scount += 1
                        performedSquat = False
                    stage = "UP"
                    feedbacks.append(("Standing: ready", (180, 180, 180)))

                # ── 2. TORSO ANGLE (shoulder-hip-knee) → chest up check ──
                if shoulder:
                    cv2.line(image, shoulder, hip, (255, 165, 0), 2)
                    torso_angle = ang((shoulder, hip), (hip, knee))
                    cv2.putText(image, f"Torso:{int(torso_angle)}d", (shoulder[0] + 5, shoulder[1] - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 165, 0), 1)
                    if torso_angle < TORSO_WARN:
                        feedbacks.append(("Chest caving forward!", (0, 80, 255)))
                    elif torso_angle < TORSO_GOOD:
                        feedbacks.append(("Chest up more!", (0, 165, 255)))
                    else:
                        feedbacks.append(("Chest up: good", (0, 210, 100)))

                # ── 3. KNEE-OVER-TOE CHECK (side view horizontal offset) ──
                knee_forward = abs(knee[0] - ankle[0])
                if knee_forward > KNEE_TOE_BAD:
                    feedbacks.append(("Knees too far forward!", (0, 80, 255)))
                elif knee_forward > KNEE_TOE_WARN:
                    feedbacks.append(("Watch your knees", (0, 165, 255)))
                else:
                    feedbacks.append(("Knee alignment: good", (0, 210, 100)))

                # ── 4. HIP DROP CHECK (at bottom of squat) ──
                # Hip y-coordinate should approach knee y at parallel depth
                if knee_angle < 130:
                    hip_drop = hip[1] - knee[1]  # positive = hip lower in image (correct)
                    if hip_drop < -30:
                        feedbacks.append(("Drop hips lower!", (0, 165, 255)))
                    else:
                        feedbacks.append(("Hip depth: good", (0, 210, 100)))

                # ── 5. FEET WIDTH HINT (both hips visible = front-facing) ──
                if 23 in idx and 24 in idx:
                    hip_width = abs(idx[23][0] - idx[24][0])
                    if hip_width < 60:
                        feedbacks.append(("Feet wider apart!", (0, 165, 255)))

            except Exception:
                feedbacks.append(("Adjust your position", (180, 180, 180)))

            if not feedbacks:
                feedbacks = [("Get into squat position", (180, 180, 180))]

            draw_panel(image, scount, stage, depth_pct, feedbacks)
            cv2.imshow('GymLytics - Squat', rescale_frame(image, percent=100))
            if cv2.waitKey(5) & 0xFF == 27:
                break

        pose.close()
        cv2.destroyAllWindows()