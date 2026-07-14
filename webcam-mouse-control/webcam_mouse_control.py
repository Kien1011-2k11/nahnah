"""Control the real mouse cursor with your index fingertip via webcam.

Run this alongside a browser tab (e.g. Fruit Ninja on Poki): while your
hand is visible the left mouse button stays held down and the cursor
follows your fingertip, so a hand swipe becomes a click-and-drag slice.
Press 'q' in the preview window to quit.

Uses MediaPipe's Tasks API (HandLandmarker) rather than the older
mp.solutions API, which recent mediapipe releases no longer ship on
some platforms/Python versions.
"""

import os
import urllib.request

import cv2
import mediapipe as mp
import pyautogui
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision

INDEX_FINGERTIP = 8
SMOOTHING = 0.5  # 0 = no smoothing, closer to 1 = smoother but laggier
HAND_LOST_GRACE_FRAMES = 5  # tolerate brief missed detections before releasing

MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hand_landmarker.task")
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/latest/hand_landmarker.task"
)

pyautogui.PAUSE = 0
pyautogui.FAILSAFE = False


def ensure_model():
    if not os.path.exists(MODEL_PATH):
        print("Đang tải model nhận diện bàn tay (chỉ tải 1 lần)...")
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        print("Tải xong.")


def make_landmarker():
    options = mp_vision.HandLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=MODEL_PATH),
        running_mode=mp_vision.RunningMode.IMAGE,
        num_hands=1,
        min_hand_detection_confidence=0.6,
        min_hand_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )
    return mp_vision.HandLandmarker.create_from_options(options)


def draw_hand(frame, hand_landmarks, frame_w, frame_h):
    points = [(int(lm.x * frame_w), int(lm.y * frame_h)) for lm in hand_landmarks]
    for x, y in points:
        cv2.circle(frame, (x, y), 3, (0, 200, 255), -1)
    tip_x, tip_y = points[INDEX_FINGERTIP]
    cv2.circle(frame, (tip_x, tip_y), 10, (0, 255, 0), -1)


def main():
    ensure_model()
    screen_w, screen_h = pyautogui.size()
    landmarker = make_landmarker()

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        raise RuntimeError("Không mở được webcam. Kiểm tra webcam có đang được ứng dụng khác dùng không.")

    smoothed_x, smoothed_y = None, None
    is_dragging = False
    frames_since_hand_seen = HAND_LOST_GRACE_FRAMES

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            frame = cv2.flip(frame, 1)  # mirror view, matches natural hand movement
            frame_h, frame_w = frame.shape[:2]
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
            result = landmarker.detect(mp_image)

            hand_seen_this_frame = bool(result.hand_landmarks)

            if hand_seen_this_frame:
                frames_since_hand_seen = 0
                landmarks = result.hand_landmarks[0]
                draw_hand(frame, landmarks, frame_w, frame_h)

                tip = landmarks[INDEX_FINGERTIP]
                target_x = tip.x * screen_w
                target_y = tip.y * screen_h

                if smoothed_x is None:
                    smoothed_x, smoothed_y = target_x, target_y
                else:
                    smoothed_x = smoothed_x * SMOOTHING + target_x * (1 - SMOOTHING)
                    smoothed_y = smoothed_y * SMOOTHING + target_y * (1 - SMOOTHING)

                pyautogui.moveTo(int(smoothed_x), int(smoothed_y))

                if not is_dragging:
                    pyautogui.mouseDown(button="left")
                    is_dragging = True
            else:
                frames_since_hand_seen += 1
                if is_dragging and frames_since_hand_seen >= HAND_LOST_GRACE_FRAMES:
                    pyautogui.mouseUp(button="left")
                    is_dragging = False
                    smoothed_x, smoothed_y = None, None

            status = "DANG CHEM (hand detected)" if hand_seen_this_frame else "Khong thay tay"
            cv2.putText(frame, status, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                        (0, 255, 0) if hand_seen_this_frame else (0, 0, 255), 2)
            cv2.putText(frame, "Nhan 'q' de thoat", (10, frame_h - 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

            cv2.imshow("Webcam Mouse Control - preview", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        if is_dragging:
            pyautogui.mouseUp(button="left")
        cap.release()
        cv2.destroyAllWindows()
        landmarker.close()


if __name__ == "__main__":
    main()
