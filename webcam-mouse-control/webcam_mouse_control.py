"""Control the real mouse cursor with your index fingertip via webcam.

Run this alongside a browser tab (e.g. Fruit Ninja on Poki). Press 'p' in
the preview window to arm/disarm hand control. While armed, the cursor
moves like a real mouse: it tracks your fingertip's *motion*, not its
absolute position, with speed-based acceleration, so small/slow hand
movement needs little arm effort and fast swipes travel further. Hold up
just your index finger, or index+middle together ("scissors" ✌, ring and
pinky curled), to hold the left mouse button down and slice; open your
palm to move the cursor without clicking. Disarm control (or show no
hand) to get your real mouse back. Press 'q' in the preview window to
quit.

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
SMOOTHING = 0.35  # 0 = no smoothing, closer to 1 = smoother but laggier
HAND_LOST_GRACE_FRAMES = 5  # tolerate brief missed detections before releasing

# Relative "real mouse" motion tuning: the cursor moves based on how fast your
# fingertip is moving, like a physical mouse, instead of jumping to an
# absolute screen position mapped from the frame. Small/slow motion needs
# little arm movement; fast swipes travel further across the screen.
DEADZONE_PX = 1.5        # ignore jitter smaller than this many frame-pixels
BASE_SENSITIVITY = 4.0   # screen-pixels moved per frame-pixel of fingertip motion
ACCEL_START_PX = 12.0    # frame-pixel speed where extra acceleration kicks in
ACCEL_GAIN = 0.35        # extra sensitivity per frame-pixel of speed above ACCEL_START_PX
MAX_SENSITIVITY = 14.0   # cap so fast swipes don't fling the cursor off-screen

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


def draw_hand(frame, hand_landmarks, frame_w, frame_h, pointing):
    points = [(int(lm.x * frame_w), int(lm.y * frame_h)) for lm in hand_landmarks]
    for x, y in points:
        cv2.circle(frame, (x, y), 3, (0, 200, 255), -1)
    tip_x, tip_y = points[INDEX_FINGERTIP]
    cv2.circle(frame, (tip_x, tip_y), 10, (0, 0, 255) if pointing else (0, 255, 0), -1)


def _dist(a, b):
    return ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5


def is_pointing_gesture(landmarks):
    """True for a click gesture: index-only ("point"), or index+middle ("scissors ✌")."""
    wrist = landmarks[0]

    def extended(tip_idx, pip_idx):
        return _dist(landmarks[tip_idx], wrist) > _dist(landmarks[pip_idx], wrist)

    index_extended = extended(8, 6)
    middle_extended = extended(12, 10)
    ring_curled = not extended(16, 14)
    pinky_curled = not extended(20, 18)

    single_finger_point = index_extended and not middle_extended
    scissors = index_extended and middle_extended
    return (single_finger_point or scissors) and ring_curled and pinky_curled


def relative_move(dx, dy):
    """Turn a raw fingertip-motion delta (frame pixels) into a mouse-like offset."""
    speed = (dx * dx + dy * dy) ** 0.5
    if speed < DEADZONE_PX:
        return 0.0, 0.0
    sensitivity = BASE_SENSITIVITY + max(0.0, speed - ACCEL_START_PX) * ACCEL_GAIN
    sensitivity = min(sensitivity, MAX_SENSITIVITY)
    return dx * sensitivity, dy * sensitivity


def main():
    ensure_model()
    landmarker = make_landmarker()

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        raise RuntimeError("Không mở được webcam. Kiểm tra webcam có đang được ứng dụng khác dùng không.")

    window_name = "Webcam Mouse Control - preview"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 1024, 768)

    smoothed_x, smoothed_y = None, None  # EMA-filtered fingertip position, in frame pixels
    remainder_x, remainder_y = 0.0, 0.0  # sub-pixel leftovers so slow motion isn't lost to rounding
    is_dragging = False
    frames_since_hand_seen = HAND_LOST_GRACE_FRAMES
    control_enabled = False

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
            pointing = False

            if hand_seen_this_frame:
                landmarks = result.hand_landmarks[0]
                pointing = is_pointing_gesture(landmarks)
                draw_hand(frame, landmarks, frame_w, frame_h, pointing)

            if control_enabled and hand_seen_this_frame:
                frames_since_hand_seen = 0
                tip = landmarks[INDEX_FINGERTIP]
                tip_x, tip_y = tip.x * frame_w, tip.y * frame_h

                if smoothed_x is None:
                    smoothed_x, smoothed_y = tip_x, tip_y
                else:
                    prev_x, prev_y = smoothed_x, smoothed_y
                    smoothed_x = smoothed_x * SMOOTHING + tip_x * (1 - SMOOTHING)
                    smoothed_y = smoothed_y * SMOOTHING + tip_y * (1 - SMOOTHING)

                    move_x, move_y = relative_move(smoothed_x - prev_x, smoothed_y - prev_y)
                    remainder_x += move_x
                    remainder_y += move_y
                    step_x, step_y = int(remainder_x), int(remainder_y)
                    remainder_x -= step_x
                    remainder_y -= step_y
                    if step_x or step_y:
                        pyautogui.moveRel(step_x, step_y)

                if pointing and not is_dragging:
                    pyautogui.mouseDown(button="left")
                    is_dragging = True
                elif not pointing and is_dragging:
                    pyautogui.mouseUp(button="left")
                    is_dragging = False
            else:
                frames_since_hand_seen += 1
                if is_dragging and frames_since_hand_seen >= HAND_LOST_GRACE_FRAMES:
                    pyautogui.mouseUp(button="left")
                    is_dragging = False
                if frames_since_hand_seen >= HAND_LOST_GRACE_FRAMES:
                    smoothed_x, smoothed_y = None, None
                    remainder_x, remainder_y = 0.0, 0.0

            control_text = "DIEU KHIEN: BAT" if control_enabled else "DIEU KHIEN: TAT (chuot binh thuong)"
            cv2.putText(frame, control_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                        (0, 255, 0) if control_enabled else (0, 165, 255), 2)
            if is_dragging:
                gesture_text = "DANG GIU CHUOT TRAI (click)"
                gesture_color = (0, 0, 255)
            elif hand_seen_this_frame:
                gesture_text = "Cu chi: TRO/KEO (se giu chuot)" if pointing else "Cu chi: BAN TAY XOE (chi di chuyen)"
                gesture_color = (0, 165, 255) if pointing else (0, 255, 0)
            else:
                gesture_text = "Khong thay tay"
                gesture_color = (128, 128, 128)
            cv2.putText(frame, gesture_text, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, gesture_color, 2)
            cv2.putText(frame, "'p' bat/tat dieu khien - 'q' thoat", (10, frame_h - 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

            cv2.imshow(window_name, frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == ord("p"):
                control_enabled = not control_enabled
                if not control_enabled and is_dragging:
                    pyautogui.mouseUp(button="left")
                    is_dragging = False
                smoothed_x, smoothed_y = None, None
                remainder_x, remainder_y = 0.0, 0.0
    finally:
        if is_dragging:
            pyautogui.mouseUp(button="left")
        cap.release()
        cv2.destroyAllWindows()
        landmarker.close()


if __name__ == "__main__":
    main()
