import math
import cv2
import numpy as np


def dot(vA, vB):
    return vA[0] * vB[0] + vA[1] * vB[1]


def ang(lineA, lineB):
    vA = [(lineA[0][0] - lineA[1][0]), (lineA[0][1] - lineA[1][1])]
    vB = [(lineB[0][0] - lineB[1][0]), (lineB[0][1] - lineB[1][1])]
    dot_prod = dot(vA, vB)
    magA = dot(vA, vA) ** 0.5
    magB = dot(vB, vB) ** 0.5
    if magA < 1e-6 or magB < 1e-6:
        return 0.0
    cos_val = np.clip(dot_prod / magA / magB, -1.0, 1.0)
    angle = math.acos(cos_val)
    ang_deg = 180 - math.degrees(angle) % 360
    return 360 - ang_deg if ang_deg - 180 >= 0 else ang_deg


def get_idx_to_coordinates(image, results, VISIBILITY_THRESHOLD=0.5, PRESENCE_THRESHOLD=0.5):
    idx_to_coordinates = {}
    image_rows, image_cols, _ = image.shape
    try:
        for idx, landmark in enumerate(results.pose_landmarks.landmark):
            if ((landmark.HasField('visibility') and
                 landmark.visibility < VISIBILITY_THRESHOLD) or
                    (landmark.HasField('presence') and
                     landmark.presence < PRESENCE_THRESHOLD)):
                continue
            landmark_px = _normalized_to_pixel_coordinates(landmark.x, landmark.y,
                                                           image_cols, image_rows)
            if landmark_px:
                idx_to_coordinates[idx] = landmark_px
    except:
        pass
    return idx_to_coordinates

def _normalized_to_pixel_coordinates(normalized_x, normalized_y, image_width, image_height):
    x_px = min(math.floor(normalized_x * image_width), image_width - 1)
    y_px = min(math.floor(normalized_y * image_height), image_height - 1)
    return x_px, y_px
