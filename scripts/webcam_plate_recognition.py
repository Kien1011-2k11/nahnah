"""Nhận diện biển số theo thời gian thực từ webcam (chạy LOCAL, không phải Kaggle).

Kaggle chạy trên server đám mây, không có quyền truy cập webcam -> phải chạy file này
trên máy tính cá nhân của bạn.

Cài đặt trước khi chạy:
    pip install ultralytics paddleocr paddlepaddle opencv-python

Chạy:
    python webcam_plate_recognition.py
"""

import re
import cv2
from ultralytics import YOLO
from paddleocr import PaddleOCR

# ⬇️ Sửa 2 dòng này
BEST_PLATE_WEIGHTS = 'best.pt'   # đường dẫn tới file best.pt đã train
CAMERA_INDEX = 0                 # 0 = webcam mặc định. Đổi thành 1, 2... nếu máy có nhiều camera

yolo_model = YOLO(BEST_PLATE_WEIGHTS)

ocr = PaddleOCR(
    use_textline_orientation=True,
    lang='en',
    enable_mkldnn=False
)

MIN_OCR_WIDTH = 200   # crop biển số nhỏ hơn ngần này (px) sẽ được phóng to trước khi đưa cho OCR


def recognize_plate(plate_img):
    if plate_img is None or plate_img.size == 0:
        return ""
    # Crop biển số ở xa thường chỉ còn vài chục pixel -> PaddleOCR không đọc nổi, trả về
    # rỗng dù YOLO vẫn detect đúng khung. Phóng to lên trước (giữ nguyên tỉ lệ) giúp OCR
    # đọc rõ chữ hơn hẳn.
    h, w = plate_img.shape[:2]
    if w < MIN_OCR_WIDTH:
        scale = MIN_OCR_WIDTH / w
        plate_img = cv2.resize(plate_img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)
    result = ocr.predict(plate_img)
    texts = []
    for res in result:
        texts.extend(res['rec_texts'])
    return " ".join(texts)


# Cặp số/chữ hay bị OCR đọc nhầm do hình dạng giống nhau.
DIGIT_LETTER_CONFUSION = {
    '0': 'D', 'D': '0',
    '2': 'Z', 'Z': '2',
    '5': 'S', 'S': '5',
    '6': 'G', 'G': '6',
    '8': 'B', 'B': '8',
}


def fix_char3(text):
    """Biển số VN: ký tự thứ 3 (không tính dấu '-', vd 51F-12345 -> 'F') luôn là CHỮ.
    Nếu OCR đọc nhầm thành số có hình dạng giống chữ (0->D, 8->B, ...) thì tự sửa lại.
    Ở CÁC VỊ TRÍ KHÁC (đáng lẽ toàn số): nếu OCR đọc nhầm thành chữ 'b' thường (dễ nhầm
    với số 6) thì tự đổi lại thành '6'. Cuối cùng chuẩn hoá toàn bộ chữ về VIẾT HOA — chữ
    trên biển số thật luôn là chữ in hoa."""
    chars = list(text)
    alnum_idx = [i for i, ch in enumerate(chars) if ch.isalnum()]
    if len(alnum_idx) < 3:
        return text.upper()
    pos3 = alnum_idx[2]
    ch = chars[pos3]
    if ch.isdigit() and ch in DIGIT_LETTER_CONFUSION:
        chars[pos3] = DIGIT_LETTER_CONFUSION[ch]

    for idx in alnum_idx:
        if idx != pos3 and chars[idx] == 'b':
            chars[idx] = '6'

    return ''.join(chars).upper()


def is_valid_plate_structure(text):
    """Đúng cấu trúc biển VN: 2 số -> 1 chữ -> còn lại toàn số (không tính dấu cách/gạch ngang)."""
    alnum_only = ''.join(ch for ch in text if ch.isalnum())
    return bool(re.fullmatch(r'\d{2}[A-Z]\d+', alnum_only))


def iou(box_a, box_b):
    """Độ chồng lấp giữa 2 khung (x1, y1, x2, y2), 0 = không chạm nhau, 1 = trùng khít."""
    xa1, ya1, xa2, ya2 = box_a
    xb1, yb1, xb2, yb2 = box_b
    inter_x1, inter_y1 = max(xa1, xb1), max(ya1, yb1)
    inter_x2, inter_y2 = min(xa2, xb2), min(ya2, yb2)
    inter = max(0, inter_x2 - inter_x1) * max(0, inter_y2 - inter_y1)
    area_a = max(0, xa2 - xa1) * max(0, ya2 - ya1)
    area_b = max(0, xb2 - xb1) * max(0, yb2 - yb1)
    return inter / (area_a + area_b - inter + 1e-6)


def valid_char_count(text):
    """Số ký tự chữ/số thật sự (bỏ dấu cách, gạch ngang) trong 1 chuỗi biển đã đọc."""
    return sum(1 for ch in text if ch.isalnum())


def plate_score(text):
    """Điểm để so sánh 2 kết quả OCR: ưu tiên đúng cấu trúc biển trước, rồi mới tới số ký
    tự đọc được (tie-break). So bằng tuple nên True > False tự động thắng."""
    return (is_valid_plate_structure(text), valid_char_count(text))


IOU_MATCH_THRESHOLD = 0.5   # 2 khung được coi là "cùng 1 biển" giữa 2 frame nếu chồng lấp >= 50%
FREEZE_FRAMES = 5           # chỉ bỏ qua OCR tối đa 5 frame liên tiếp cho cùng 1 biển
MIN_VALID_CHARS = 8         # chỉ tin dùng lại chữ cũ nếu lần đọc trước đó có >= 8 ký tự

cap = cv2.VideoCapture(CAMERA_INDEX)
if not cap.isOpened():
    raise RuntimeError(
        f"Không mở được camera (index={CAMERA_INDEX}).\n"
        f"-> Kiểm tra: (1) camera có đang bị app khác chiếm dụng không, "
        f"(2) thử đổi CAMERA_INDEX sang 1, 2... nếu máy có nhiều camera."
    )

# Các biển đang theo dõi: mỗi biển có id riêng, khung vị trí, chữ đọc tốt nhất từng thấy,
# và số frame liên tiếp đã "ăn theo" chữ cũ (khỏi OCR lại) kể từ lần OCR gần nhất.
tracked_plates = []   # [{'id', 'box', 'text', 'frames_reused'}, ...]
next_id = 1

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    yolo_results = yolo_model(frame, verbose=False)[0]

    new_tracked = []
    for box in yolo_results.boxes:
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        cur_box = (x1, y1, x2, y2)

        # Tìm biển đã theo dõi ở frame trước khớp vị trí nhất (IoU cao nhất, >= ngưỡng)
        best_match, best_iou = None, IOU_MATCH_THRESHOLD
        for tp in tracked_plates:
            i = iou(cur_box, tp['box'])
            if i >= best_iou:
                best_match, best_iou = tp, i

        if best_match is not None:
            plate_id = best_match['id']
            prev_text = best_match['text']
            can_reuse = (
                best_match['frames_reused'] < FREEZE_FRAMES
                and is_valid_plate_structure(prev_text)
            )
        else:
            plate_id = next_id
            next_id += 1
            prev_text = ""
            can_reuse = False

        if can_reuse:
            text = prev_text
            frames_reused = best_match['frames_reused'] + 1
        else:
            plate_crop = frame[y1:y2, x1:x2]
            new_text = fix_char3(recognize_plate(plate_crop))
            # Chỉ chấp nhận kết quả OCR mới nếu điểm không tệ hơn chữ đã đọc trước đó.
            text = new_text if plate_score(new_text) >= plate_score(prev_text) else prev_text
            frames_reused = 0

        new_tracked.append({'id': plate_id, 'box': cur_box, 'text': text, 'frames_reused': frames_reused})

        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(frame, text, (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

    tracked_plates = new_tracked

    cv2.imshow('License Plate Recognition (nhấn q để thoát)', frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
