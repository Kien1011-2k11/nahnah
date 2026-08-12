"""Web app nhận diện biển số - chạy LOCAL trên máy bạn.

Cài đặt:
    pip install flask ultralytics paddleocr paddlepaddle opencv-python

Chạy:
    ANPR_WEIGHTS=/duong/dan/toi/best.pt python app.py

Rồi mở trình duyệt vào: http://127.0.0.1:5000
"""

import os
import uuid
import threading

from flask import Flask, request, jsonify, send_from_directory, render_template

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
OUTPUT_DIR = os.path.join(BASE_DIR, 'outputs')
CROPS_DIR = os.path.join(OUTPUT_DIR, 'crops')
for d in (UPLOAD_DIR, OUTPUT_DIR, CROPS_DIR):
    os.makedirs(d, exist_ok=True)

# ⬇️ Sửa đường dẫn này hoặc set biến môi trường ANPR_WEIGHTS khi chạy
WEIGHTS_PATH = os.environ.get('ANPR_WEIGHTS', os.path.join(BASE_DIR, 'best.pt'))

app = Flask(__name__)

job = {
    'status': 'idle',   # idle | processing | done | error
    'progress': 0.0,
    'results': [],
    'output_video': None,
    'error': None,
}
job_lock = threading.Lock()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/upload', methods=['POST'])
def upload():
    if 'video' not in request.files:
        return jsonify({'error': 'Không có file video'}), 400
    f = request.files['video']
    if f.filename == '':
        return jsonify({'error': 'Chưa chọn file'}), 400

    with job_lock:
        if job['status'] == 'processing':
            return jsonify({'error': 'Đang xử lý video khác, đợi xong đã'}), 409
        job.update({'status': 'processing', 'progress': 0.0, 'results': [], 'output_video': None, 'error': None})

    if not os.path.isfile(WEIGHTS_PATH):
        with job_lock:
            job['status'] = 'error'
            job['error'] = f"Không tìm thấy file weights: {WEIGHTS_PATH} (sửa WEIGHTS_PATH trong app.py hoặc set biến môi trường ANPR_WEIGHTS)"
        return jsonify({'error': job['error']}), 400

    job_id = uuid.uuid4().hex[:8]
    ext = os.path.splitext(f.filename)[1] or '.mp4'
    in_path = os.path.join(UPLOAD_DIR, f'{job_id}{ext}')
    out_path = os.path.join(OUTPUT_DIR, f'{job_id}_result.mp4')
    f.save(in_path)

    thread = threading.Thread(target=run_job, args=(in_path, out_path, job_id), daemon=True)
    thread.start()

    return jsonify({'status': 'processing'})


def run_job(in_path, out_path, job_id):
    from detector import process_video
    try:
        process_video(in_path, out_path, WEIGHTS_PATH, job, job_lock, CROPS_DIR, job_id)
        with job_lock:
            job['status'] = 'done'
            job['output_video'] = f'/outputs/{os.path.basename(out_path)}'
    except Exception as e:
        with job_lock:
            job['status'] = 'error'
            job['error'] = str(e)


@app.route('/api/status')
def status():
    with job_lock:
        return jsonify({
            'status': job['status'],
            'progress': job['progress'],
            'output_video': job['output_video'],
            'error': job['error'],
            'total': len(job['results']),
        })


@app.route('/api/results')
def results():
    with job_lock:
        return jsonify(job['results'])


@app.route('/outputs/<path:filename>')
def outputs(filename):
    return send_from_directory(OUTPUT_DIR, filename)


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=False)
