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

# Elbow angle thresholds (shoulder-elbow-wrist, side view)
# UP:   elbow ~160-180 deg (arms fully extended)
# DOWN: elbow ~70-90 deg   (chest near floor, proper depth)
ELBOW_UP   = 155
ELBOW_DOWN = 90

# Body line (shoulder-hip-ankle): proper plank = ~170-185 deg
BODY_MIN = 160
BODY_MAX = 195


def draw_panel(image, count, stage, depth_pct, feedbacks):
    h = image.shape[0]
    overlay = image.copy()
    cv2.rectangle(overlay, (0, 0), (320, h), (20, 20, 20), -1)
    cv2.addWeighted(overlay, 0.55, image, 0.45, 0, image)

    cv2.putText(image, "GYMLYTICS", (10, 35), cv2.FONT_HERSHEY_DUPLEX, 0.9, (0, 200, 255), 2)
    cv2.putText(image, "Push Up", (10, 58), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (160, 160, 160), 1)
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


class Pushup(Exercise):
    def __init__(self):
        pass

    def exercise(self, source):
        threaded_camera = ThreadedCamera(source)
        time.sleep(1)

        scount = 0
        performedPushUp = False
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
                # Side view: prefer left side landmarks, fallback right
                if 12 in idx and 14 in idx and 16 in idx:
                    shoulder, elbow, wrist = idx[12], idx[14], idx[16]
                    hip, ankle = idx.get(24), idx.get(28)
                elif 11 in idx and 13 in idx and 15 in idx:
                    shoulder, elbow, wrist = idx[11], idx[13], idx[15]
                    hip, ankle = idx.get(23), idx.get(27)
                else:
                    feedbacks = [("No pose detected", (0, 80, 255)),
                                 ("Face camera from the side", (180, 180, 180))]
                    draw_panel(image, scount, stage, depth_pct, feedbacks)
                    cv2.imshow('GymLytics - Push Up', rescale_frame(image, percent=100))
                    if cv2.waitKey(5) & 0xFF == 27:
                        break
                    continue

                # Draw arm lines
                cv2.line(image, shoulder, elbow, (255, 0, 255), 4)
                cv2.line(image, elbow, wrist, (255, 0, 255), 4)
                cv2.circle(image, elbow, 8, (0, 255, 255), cv2.FILLED)

                # ── 1. ELBOW ANGLE → rep counting ──
                elbow_angle = ang((shoulder, elbow), (elbow, wrist))
                cv2.putText(image, f"Elbow:{int(elbow_angle)}d", (elbow[0] + 5, elbow[1] - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 0), 2)

                depth_pct = float(np.clip(np.interp(elbow_angle, (ELBOW_DOWN, ELBOW_UP), (100, 0)), 0, 100))

                try:
                    l1 = np.linspace(shoulder, elbow, 100)
                    l2 = np.linspace(elbow, wrist, 100)
                    center, radius, sa, ea = convert_arc(l1[80], l2[20], sagitta=15)
                    draw_ellipse(image, center, (radius, radius), -1, sa, ea, 255)
                except Exception:
                    pass

                if elbow_angle <= ELBOW_DOWN:
                    stage = "DOWN"
                    performedPushUp = True
                    feedbacks.append(("Great depth!", (0, 210, 100)))
                elif elbow_angle < ELBOW_UP:
                    stage = "DOWN"
                    feedbacks.append(("Go lower!", (0, 165, 255)))
                else:
                    if performedPushUp:
                        scount += 1
                        performedPushUp = False
                    stage = "UP"
                    feedbacks.append(("Arms extended: ready", (0, 210, 100)))

                # ── 2. BODY ALIGNMENT (shoulder-hip-ankle, fallback to shoulder-hip-knee) ──
                # Use ankle if visible, otherwise knee as fallback — ensures check always runs
                knee_pt = idx.get(26) or idx.get(25)
                ref_pt = ankle if ankle else knee_pt
                if hip and ref_pt:
                    cv2.line(image, shoulder, hip, (255, 165, 0), 2)
                    cv2.line(image, hip, ref_pt, (255, 165, 0), 2)
                    body_angle = ang((shoulder, hip), (hip, ref_pt))
                    if body_angle < BODY_MIN:
                        feedbacks.append(("Hips sagging!", (0, 80, 255)))
                    elif body_angle > BODY_MAX:
                        feedbacks.append(("Hips too high!", (0, 80, 255)))
                    else:
                        feedbacks.append(("Body straight: good", (0, 210, 100)))
                else:
                    feedbacks.append(("Show full body sideways", (180, 180, 180)))

                # ── 3. ELBOW FLARE (mid-rep only) ──
                if elbow_angle < 130:
                    flare = abs(elbow[0] - shoulder[0])
                    if flare > 80:
                        feedbacks.append(("Tuck elbows in!", (0, 80, 255)))
                    else:
                        feedbacks.append(("Elbows: good", (0, 210, 100)))

                # ── 4. HEAD POSITION ──
                if 0 in idx:
                    if idx[0][1] > shoulder[1] + 45:
                        feedbacks.append(("Head dropping!", (0, 80, 255)))
                    else:
                        feedbacks.append(("Head neutral: good", (0, 210, 100)))

            except Exception:
                feedbacks.append(("Adjust your position", (180, 180, 180)))

            if not feedbacks:
                feedbacks = [("Get into push-up position", (180, 180, 180))]

            draw_panel(image, scount, stage, depth_pct, feedbacks)
            cv2.imshow('GymLytics - Push Up', rescale_frame(image, percent=100))
            if cv2.waitKey(5) & 0xFF == 27:
                break

        pose.close()
        cv2.destroyAllWindows()