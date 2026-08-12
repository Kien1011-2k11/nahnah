"""Xử lý video: YOLO detect biển số -> PaddleOCR đọc chữ -> theo dõi biển qua các frame.

Logic nhận diện/đọc chữ giữ nguyên như notebook và webcam_plate_recognition.py (cùng bộ quy
tắc sửa lỗi ký tự, ưu tiên cấu trúc biển, cache OCR có giới hạn frame). File này chỉ thêm phần
ghi kết quả (ảnh xe/ảnh biển + text) ra để web hiển thị, và vẽ khung theo đúng phong cách 2 lớp
(khung ngoài màu hồng ghi kích thước px, khung trong màu xanh ghi chữ biển) giống giao diện mẫu.
"""

import os
import re
import time
import cv2
import numpy as np

MIN_OCR_WIDTH = 200
IOU_MATCH_THRESHOLD = 0.5
FREEZE_FRAMES = 5
MIN_VALID_CHARS = 8

DIGIT_LETTER_CONFUSION = {
    '0': 'D', 'D': '0',
    '2': 'Z', 'Z': '2',
    '5': 'S', 'S': '5',
    '6': 'G', 'G': '6',
    '8': 'B', 'B': '8',
}


def fix_char3(text):
    """Biển số VN: ký tự thứ 3 luôn là CHỮ, các vị trí khác toàn số; b thường -> 6; viết hoa hết."""
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
    alnum_only = ''.join(ch for ch in text if ch.isalnum())
    return bool(re.fullmatch(r'\d{2}[A-Z]\d+', alnum_only))


def iou(box_a, box_b):
    xa1, ya1, xa2, ya2 = box_a
    xb1, yb1, xb2, yb2 = box_b
    inter_x1, inter_y1 = max(xa1, xb1), max(ya1, yb1)
    inter_x2, inter_y2 = min(xa2, xb2), min(ya2, yb2)
    inter = max(0, inter_x2 - inter_x1) * max(0, inter_y2 - inter_y1)
    area_a = max(0, xa2 - xa1) * max(0, ya2 - ya1)
    area_b = max(0, xb2 - xb1) * max(0, yb2 - yb1)
    return inter / (area_a + area_b - inter + 1e-6)


def valid_char_count(text):
    return sum(1 for ch in text if ch.isalnum())


def plate_score(text):
    return (is_valid_plate_structure(text), valid_char_count(text))


class ANPRModel:
    """Load YOLO + PaddleOCR một lần duy nhất, dùng lại cho mọi video."""
    _yolo = None
    _ocr = None

    @classmethod
    def get(cls, weights_path):
        if cls._yolo is None:
            from ultralytics import YOLO
            cls._yolo = YOLO(weights_path)
        if cls._ocr is None:
            from paddleocr import PaddleOCR
            cls._ocr = PaddleOCR(use_textline_orientation=True, lang='en', enable_mkldnn=False)
        return cls._yolo, cls._ocr


def recognize_plate(ocr, plate_img):
    if plate_img is None or plate_img.size == 0:
        return ""
    h, w = plate_img.shape[:2]
    if w < MIN_OCR_WIDTH:
        scale = MIN_OCR_WIDTH / w
        plate_img = cv2.resize(plate_img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)
    result = ocr.predict(plate_img)
    texts = []
    for res in result:
        texts.extend(res['rec_texts'])
    return " ".join(texts)


def _draw_boxes(frame, x1, y1, x2, y2, text):
    """Khung hồng ngoài (kích thước px) + khung xanh trong (chữ biển), giống giao diện mẫu."""
    bw, bh = x2 - x1, y2 - y1
    magenta = (203, 0, 203)
    green = (0, 200, 0)

    cv2.rectangle(frame, (x1, y1), (x2, y2), magenta, 2)
    dim_label = f"{bw}x{bh}"
    (tw, th), _ = cv2.getTextSize(dim_label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
    cv2.rectangle(frame, (x1, max(0, y1 - th - 8)), (x1 + tw + 6, y1), magenta, -1)
    cv2.putText(frame, dim_label, (x1 + 3, max(12, y1 - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    if text:
        inset = 4
        ix1, iy1 = x1 + inset, y1 + inset
        ix2, iy2 = x2 - inset, y2 - inset
        if ix2 > ix1 and iy2 > iy1:
            cv2.rectangle(frame, (ix1, iy1), (ix2, iy2), green, 2)
        cv2.putText(frame, text, (x1, y2 + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.65, green, 2)


def process_video(video_path, output_path, weights_path, job, job_lock, crops_dir, job_id):
    """Chạy detect+OCR trên toàn bộ video, ghi video kết quả ra output_path, và mỗi khi 1 biển
    mới được đọc đủ tin cậy lần đầu thì thêm 1 dòng vào job['results'] (thread-safe qua job_lock)
    để frontend poll thấy ngay, không cần đợi xử lý xong hết video."""
    yolo, ocr = ANPRModel.get(weights_path)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Không mở được video đầu vào: {video_path}")

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    writer = cv2.VideoWriter(output_path, fourcc, fps, (frame_w, frame_h))
    if not writer.isOpened():
        cap.release()
        raise RuntimeError(f"Không mở được VideoWriter để ghi ra: {output_path}")

    tracked_plates = []
    next_id = 1
    emitted_plate_texts = set()   # ⭐ chặn theo TEXT đã đọc được, không phải theo track_id -> xe
                                    #   rời khung rồi quay lại (track_id đổi) vẫn không bị in lại
    result_seq = 0
    frame_idx = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        frame_idx += 1
        clean_frame = frame.copy()   # crop ảnh xe/biển từ đây, tránh dính khung màu đã vẽ

        yolo_results = yolo(frame, verbose=False)[0]
        new_tracked = []

        for box in yolo_results.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(frame_w, x2), min(frame_h, y2)
            if x2 <= x1 or y2 <= y1:
                continue
            cur_box = (x1, y1, x2, y2)

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
                    and valid_char_count(prev_text) >= MIN_VALID_CHARS
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
                crop = clean_frame[y1:y2, x1:x2]
                new_text = fix_char3(recognize_plate(ocr, crop))
                text = new_text if plate_score(new_text) >= plate_score(prev_text) else prev_text
                frames_reused = 0

            new_tracked.append({'id': plate_id, 'box': cur_box, 'text': text, 'frames_reused': frames_reused})
            _draw_boxes(frame, x1, y1, x2, y2, text)

            if (
                text not in emitted_plate_texts
                and valid_char_count(text) >= MIN_VALID_CHARS
                and is_valid_plate_structure(text)
            ):
                emitted_plate_texts.add(text)
                result_seq += 1
                bw, bh = x2 - x1, y2 - y1
                vx1 = max(0, x1 - bw)
                vy1 = max(0, y1 - bh)
                vx2 = min(frame_w, x2 + bw)
                vy2 = min(frame_h, y2 + bh)
                vehicle_crop = clean_frame[vy1:vy2, vx1:vx2]
                plate_crop = clean_frame[y1:y2, x1:x2]

                seq = result_seq
                vehicle_name = f"{job_id}_{seq}_vehicle.jpg"
                plate_name = f"{job_id}_{seq}_plate.jpg"
                cv2.imwrite(os.path.join(crops_dir, vehicle_name), vehicle_crop)
                cv2.imwrite(os.path.join(crops_dir, plate_name), plate_crop)

                with job_lock:
                    job['results'].append({
                        'id': plate_id,
                        'seq': seq,
                        'plate_text': text,
                        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                        'vehicle_image': f'/outputs/crops/{vehicle_name}',
                        'plate_image': f'/outputs/crops/{plate_name}',
                    })

        tracked_plates = new_tracked
        writer.write(frame)

        if total_frames:
            with job_lock:
                job['progress'] = frame_idx / total_frames

    cap.release()
    writer.release()
