import urllib.request
url = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task"
urllib.request.urlretrieve(url, "pose_landmarker.task")
print("Done!")