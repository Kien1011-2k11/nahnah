const dropzone = document.getElementById('dropzone');
const fileInput = document.getElementById('fileInput');
const chooseBtn = document.getElementById('chooseBtn');
const processingView = document.getElementById('processing');
const processingText = document.getElementById('processingText');
const progressFill = document.getElementById('progressFill');
const resultVideo = document.getElementById('resultVideo');
const errorBox = document.getElementById('errorBox');
const resultsList = document.getElementById('resultsList');
const totalCount = document.getElementById('totalCount');
const searchInput = document.getElementById('searchInput');
const searchBtn = document.getElementById('searchBtn');

let pollTimer = null;
let allResults = [];

function showView(view) {
  dropzone.hidden = view !== 'dropzone';
  processingView.hidden = view !== 'processing';
  resultVideo.hidden = view !== 'video';
}

function showError(msg) {
  errorBox.hidden = false;
  errorBox.textContent = msg;
}

function clearError() {
  errorBox.hidden = true;
  errorBox.textContent = '';
}

chooseBtn.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', () => {
  if (fileInput.files.length) uploadFile(fileInput.files[0]);
});

['dragover', 'dragenter'].forEach(evt =>
  dropzone.addEventListener(evt, e => {
    e.preventDefault();
    dropzone.style.borderColor = '#4a7bb5';
  })
);
['dragleave', 'drop'].forEach(evt =>
  dropzone.addEventListener(evt, e => {
    e.preventDefault();
    dropzone.style.borderColor = '';
  })
);
dropzone.addEventListener('drop', e => {
  const files = e.dataTransfer.files;
  if (files.length) uploadFile(files[0]);
});

function uploadFile(file) {
  clearError();
  resultsList.innerHTML = '';
  allResults = [];
  totalCount.textContent = '0';

  const formData = new FormData();
  formData.append('video', file);

  showView('processing');
  processingText.textContent = 'Đang tải lên & phân tích video...';
  progressFill.style.width = '0%';

  fetch('/api/upload', { method: 'POST', body: formData })
    .then(res => res.json().then(data => ({ ok: res.ok, data })))
    .then(({ ok, data }) => {
      if (!ok) {
        showView('dropzone');
        showError(data.error || 'Có lỗi khi tải video lên');
        return;
      }
      startPolling();
    })
    .catch(err => {
      showView('dropzone');
      showError('Không kết nối được tới server: ' + err.message);
    });
}

function startPolling() {
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(pollStatus, 1000);
  pollStatus();
}

function pollStatus() {
  fetch('/api/status')
    .then(res => res.json())
    .then(data => {
      if (data.status === 'processing') {
        const pct = Math.round((data.progress || 0) * 100);
        progressFill.style.width = pct + '%';
        processingText.textContent = `Đang phân tích video... ${pct}%`;
      } else if (data.status === 'done') {
        clearInterval(pollTimer);
        resultVideo.src = data.output_video;
        showView('video');
        resultVideo.play().catch(() => {});
      } else if (data.status === 'error') {
        clearInterval(pollTimer);
        showView('dropzone');
        showError(data.error || 'Xử lý video thất bại');
      }
      totalCount.textContent = data.total || 0;
    })
    .catch(() => {});

  fetch('/api/results')
    .then(res => res.json())
    .then(renderResults)
    .catch(() => {});
}

function renderResults(results) {
  allResults = results;
  applyFilter();
}

function applyFilter() {
  const q = searchInput.value.trim().toLowerCase();
  const filtered = q
    ? allResults.filter(r => r.plate_text.toLowerCase().includes(q))
    : allResults;

  resultsList.innerHTML = filtered
    .slice()
    .reverse()
    .map(r => `
      <div class="result-card">
        <img src="${r.vehicle_image}" alt="xe">
        <img src="${r.plate_image}" alt="bien so">
        <div class="info">
          <div><span class="seq">${r.seq}</span><span class="plate-text">${r.plate_text}</span></div>
          <div class="meta">${r.timestamp}</div>
        </div>
        <span class="check">✔</span>
      </div>
    `)
    .join('');
}

searchInput.addEventListener('input', applyFilter);
searchBtn.addEventListener('click', applyFilter);
