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

# Plank body line: shoulder(11)-hip(23)-ankle(27), side view
# Perfect plank: angle ~170-185 deg (dead straight)
# Hips too high: angle > 185 deg
# Hips sagging:  angle < 160 deg
PLANK_GOOD_MIN = 165
PLANK_GOOD_MAX = 185
PLANK_ACTIVE   = 160   # minimum to start timer


def draw_panel(image, duration, body_angle, align_pct, feedbacks):
    h = image.shape[0]
    overlay = image.copy()
    cv2.rectangle(overlay, (0, 0), (320, h), (20, 20, 20), -1)
    cv2.addWeighted(overlay, 0.55, image, 0.45, 0, image)

    cv2.putText(image, "GYMLYTICS", (10, 35), cv2.FONT_HERSHEY_DUPLEX, 0.9, (0, 200, 255), 2)
    cv2.putText(image, "Plank", (10, 58), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (160, 160, 160), 1)
    cv2.line(image, (10, 68), (310, 68), (60, 60, 60), 1)

    cv2.putText(image, "TIME (sec)", (10, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (160, 160, 160), 1)
    cv2.putText(image, str(int(duration)), (10, 160), cv2.FONT_HERSHEY_DUPLEX, 2.8, (0, 255, 150), 4)

    ac = (0, 210, 100) if align_pct > 75 else (0, 165, 255) if align_pct > 40 else (0, 80, 255)
    cv2.putText(image, f"Alignment: {int(align_pct)}%", (10, 190), cv2.FONT_HERSHEY_SIMPLEX, 0.5, ac, 1)
    cv2.rectangle(image, (10, 197), (310, 210), (60, 60, 60), -1)
    cv2.rectangle(image, (10, 197), (10 + int(align_pct * 3.0), 210), ac, -1)

    cv2.putText(image, f"Body angle: {int(body_angle)}d", (10, 230),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1)

    cv2.line(image, (10, 240), (310, 240), (60, 60, 60), 1)
    cv2.putText(image, "FEEDBACK", (10, 260), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (160, 160, 160), 1)
    for i, (msg, color) in enumerate(feedbacks[:7]):
        cv2.putText(image, msg, (10, 286 + i * 27), cv2.FONT_HERSHEY_SIMPLEX, 0.49, color, 1)
    cv2.putText(image, "ESC to quit", (10, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (100, 100, 100), 1)


class Plank(Exercise):
    def __init__(self):
        pass

    def exercise(self, source):
        threaded_camera = ThreadedCamera(source)
        time.sleep(1)

        body_angle = 0.0
        plankTimer = None
        plankDuration = 0.0

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
            align_pct = 0.0

            try:
                # Side view: shoulder(11)-hip(23)-ankle(27) left body line
                # Fallback: right side 12-24-28
                if 11 in idx and 23 in idx and 27 in idx:
                    shoulder, hip, ankle = idx[11], idx[23], idx[27]
                elif 12 in idx and 24 in idx and 28 in idx:
                    shoulder, hip, ankle = idx[12], idx[24], idx[28]
                else:
                    feedbacks = [("No pose detected", (0, 80, 255)),
                                 ("Face camera from the side", (180, 180, 180))]
                    draw_panel(image, plankDuration, body_angle, align_pct, feedbacks)
                    cv2.imshow('GymLytics - Plank', rescale_frame(image, percent=100))
                    if cv2.waitKey(5) & 0xFF == 27:
                        break
                    continue

                # Draw body line
                cv2.line(image, shoulder, hip, (255, 0, 0), 5)
                cv2.line(image, hip, ankle, (255, 0, 0), 5)
                cv2.circle(image, shoulder, 10, (0, 0, 255), cv2.FILLED)
                cv2.circle(image, hip, 10, (0, 0, 255), cv2.FILLED)
                cv2.circle(image, ankle, 10, (0, 0, 255), cv2.FILLED)

                # ── 1. BODY LINE ANGLE (shoulder-hip-ankle) ──
                body_angle = ang((shoulder, hip), (hip, ankle))
                cv2.putText(image, f"{int(body_angle)}d", (hip[0] + 10, hip[1] - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

                # Alignment %: 120 deg = 0%, 175 deg = 100%
                align_pct = float(np.clip(np.interp(body_angle, (120, 175), (0, 100)), 0, 100))

                # ── 2. TIMER: only run when body is straight ──
                if body_angle >= PLANK_ACTIVE:
                    if plankTimer is None:
                        plankTimer = time.time()
                    plankDuration += time.time() - plankTimer
                    plankTimer = time.time()
                    feedbacks.append(("Plank active! Hold!", (0, 210, 100)))
                else:
                    plankTimer = None
                    feedbacks.append(("Fix form to start timer", (0, 80, 255)))

                # ── 3. HIP POSITION FEEDBACK ──
                if body_angle > PLANK_GOOD_MAX:
                    feedbacks.append(("Hips too high!", (0, 80, 255)))
                elif body_angle < PLANK_GOOD_MIN:
                    if body_angle < 150:
                        feedbacks.append(("Hips badly sagging!", (0, 80, 255)))
                    else:
                        feedbacks.append(("Hips slightly low", (0, 165, 255)))
                else:
                    feedbacks.append(("Hip position: perfect", (0, 210, 100)))

                # ── 4. HEAD POSITION ──
                if 0 in idx:
                    head = idx[0]
                    head_drop = head[1] - shoulder[1]
                    if head_drop > 40:
                        feedbacks.append(("Head drooping!", (0, 80, 255)))
                    elif head_drop < -40:
                        feedbacks.append(("Head too high!", (0, 165, 255)))
                    else:
                        feedbacks.append(("Head neutral: good", (0, 210, 100)))

                # ── 5. SHOULDER OVER WRIST CHECK ──
                # In a plank, wrist should be roughly below shoulder (front view)
                wrist = idx.get(15) or idx.get(16)
                if wrist:
                    sh_wrist_offset = abs(shoulder[0] - wrist[0])
                    if sh_wrist_offset > 80:
                        feedbacks.append(("Hands under shoulders!", (0, 165, 255)))
                    else:
                        feedbacks.append(("Hand position: good", (0, 210, 100)))

                # ── 6. CORE HINT ──
                if body_angle >= PLANK_GOOD_MIN and body_angle <= PLANK_GOOD_MAX:
                    feedbacks.append(("Core engaged!", (0, 210, 100)))
                else:
                    feedbacks.append(("Engage your core!", (0, 165, 255)))

            except Exception:
                feedbacks.append(("Adjust your position", (180, 180, 180)))

            if not feedbacks:
                feedbacks = [("Get into plank position", (180, 180, 180))]

            draw_panel(image, plankDuration, body_angle, align_pct, feedbacks)
            cv2.imshow('GymLytics - Plank', rescale_frame(image, percent=100))
            if cv2.waitKey(5) & 0xFF == 27:
                break

        pose.close()
        cv2.destroyAllWindows()