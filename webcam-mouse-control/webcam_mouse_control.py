"""Control the real mouse cursor with your index fingertip via webcam.

Run this alongside a browser tab (e.g. Fruit Ninja on Poki): while your
hand is visible the left mouse button stays held down and the cursor
follows your fingertip, so a hand swipe becomes a click-and-drag slice.
Press 'q' in the preview window to quit.
"""

import cv2
import mediapipe as mp
import pyautogui

INDEX_FINGERTIP = 8
SMOOTHING = 0.5  # 0 = no smoothing, closer to 1 = smoother but laggier
HAND_LOST_GRACE_FRAMES = 5  # tolerate brief missed detections before releasing

pyautogui.PAUSE = 0
pyautogui.FAILSAFE = False


def main():
    screen_w, screen_h = pyautogui.size()

    hands = mp.solutions.hands.Hands(
        static_image_mode=False,
        max_num_hands=1,
        min_detection_confidence=0.6,
        min_tracking_confidence=0.5,
    )
    drawer = mp.solutions.drawing_utils

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
            results = hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

            hand_seen_this_frame = bool(results.multi_hand_landmarks)

            if hand_seen_this_frame:
                frames_since_hand_seen = 0
                landmarks = results.multi_hand_landmarks[0]
                drawer.draw_landmarks(frame, landmarks, mp.solutions.hands.HAND_CONNECTIONS)

                tip = landmarks.landmark[INDEX_FINGERTIP]
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

                cv2.circle(frame, (int(tip.x * frame_w), int(tip.y * frame_h)), 10, (0, 255, 0), -1)
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
        hands.close()


if __name__ == "__main__":
    main()
