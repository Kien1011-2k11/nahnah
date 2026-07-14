const videoEl = document.getElementById("webcam");
const canvas = document.getElementById("game");
const ctx = canvas.getContext("2d");

const scoreEl = document.getElementById("score");
const livesEl = document.getElementById("lives");
const handStatusEl = document.getElementById("handStatus");
const menuEl = document.getElementById("menu");
const gameOverEl = document.getElementById("gameOver");
const startBtn = document.getElementById("startBtn");
const restartBtn = document.getElementById("restartBtn");
const camErrorEl = document.getElementById("camError");
const finalScoreEl = document.getElementById("finalScore");
const highScoreEl = document.getElementById("highScore");

const FRUIT_TYPES = [
  { emoji: "🍉", radius: 46 },
  { emoji: "🍊", radius: 38 },
  { emoji: "🍎", radius: 38 },
  { emoji: "🍋", radius: 34 },
  { emoji: "🍓", radius: 32 },
  { emoji: "🥝", radius: 34 },
  { emoji: "🍍", radius: 42 },
];
const BOMB = { emoji: "💣", radius: 40 };

const GRAVITY = 0.32;
const MAX_LIVES = 3;
const SPAWN_INTERVAL_MS = 950;
const FINGER_TRAIL_LENGTH = 6;

let state = "menu"; // menu | playing | gameover
let score = 0;
let lives = MAX_LIVES;
let fruits = [];
let particles = [];
let fingerTrail = [];
let lastSpawnTime = 0;
let animationHandle = null;

function resizeCanvas() {
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;
}
window.addEventListener("resize", resizeCanvas);
resizeCanvas();

function updateHud() {
  scoreEl.textContent = `Điểm: ${score}`;
  livesEl.textContent = "❤️".repeat(Math.max(lives, 0)) + "🖤".repeat(MAX_LIVES - Math.max(lives, 0));
}

function spawnFruit() {
  const isBomb = Math.random() < 0.12;
  const template = isBomb ? BOMB : FRUIT_TYPES[Math.floor(Math.random() * FRUIT_TYPES.length)];
  const x = 80 + Math.random() * (canvas.width - 160);
  const launchSpeed = 12 + Math.random() * 4;
  fruits.push({
    x,
    y: canvas.height + 40,
    vx: (Math.random() - 0.5) * 4,
    vy: -launchSpeed,
    radius: template.radius,
    emoji: template.emoji,
    isBomb,
    rotation: Math.random() * Math.PI * 2,
    rotationSpeed: (Math.random() - 0.5) * 0.1,
    sliced: false,
  });
}

function spawnJuice(x, y, count = 10) {
  for (let i = 0; i < count; i++) {
    const angle = Math.random() * Math.PI * 2;
    const speed = 2 + Math.random() * 5;
    particles.push({
      x,
      y,
      vx: Math.cos(angle) * speed,
      vy: Math.sin(angle) * speed - 2,
      life: 1,
      decay: 0.02 + Math.random() * 0.02,
      size: 4 + Math.random() * 4,
      color: `hsl(${Math.floor(Math.random() * 40) + 340}, 80%, 55%)`,
    });
  }
}

function spawnHalves(fruit) {
  particles.push({
    isHalf: true,
    emoji: fruit.emoji,
    x: fruit.x,
    y: fruit.y,
    vx: -4 - Math.random() * 2,
    vy: fruit.vy - 3,
    rotation: fruit.rotation,
    rotationSpeed: -0.15,
    radius: fruit.radius,
    life: 1,
    decay: 0.012,
  });
  particles.push({
    isHalf: true,
    emoji: fruit.emoji,
    x: fruit.x,
    y: fruit.y,
    vx: 4 + Math.random() * 2,
    vy: fruit.vy - 3,
    rotation: fruit.rotation,
    rotationSpeed: 0.15,
    radius: fruit.radius,
    life: 1,
    decay: 0.012,
  });
}

function distToSegment(px, py, ax, ay, bx, by) {
  const dx = bx - ax;
  const dy = by - ay;
  const lenSq = dx * dx + dy * dy;
  let t = lenSq === 0 ? 0 : ((px - ax) * dx + (py - ay) * dy) / lenSq;
  t = Math.max(0, Math.min(1, t));
  const cx = ax + t * dx;
  const cy = ay + t * dy;
  return Math.hypot(px - cx, py - cy);
}

function checkSlices() {
  if (fingerTrail.length < 2) return;
  const [prev, curr] = fingerTrail.slice(-2);
  const speed = Math.hypot(curr.x - prev.x, curr.y - prev.y);
  if (speed < 6) return; // require a real swipe, not a still finger

  let slicedAny = false;
  for (const fruit of fruits) {
    if (fruit.sliced) continue;
    const d = distToSegment(fruit.x, fruit.y, prev.x, prev.y, curr.x, curr.y);
    if (d <= fruit.radius) {
      fruit.sliced = true;
      slicedAny = true;
      if (fruit.isBomb) {
        endGame();
        return;
      }
      score += 1;
      spawnJuice(fruit.x, fruit.y);
      spawnHalves(fruit);
    }
  }
  if (slicedAny) updateHud();
}

function endGame() {
  state = "gameover";
  const best = Math.max(score, Number(localStorage.getItem("fruitNinjaHighScore") || 0));
  localStorage.setItem("fruitNinjaHighScore", String(best));
  finalScoreEl.textContent = `Điểm: ${score}`;
  highScoreEl.textContent = `Điểm cao nhất: ${best}`;
  gameOverEl.classList.remove("hidden");
}

function update(dt) {
  const now = performance.now();
  if (now - lastSpawnTime > SPAWN_INTERVAL_MS) {
    spawnFruit();
    lastSpawnTime = now;
  }

  for (const fruit of fruits) {
    fruit.x += fruit.vx;
    fruit.y += fruit.vy;
    fruit.vy += GRAVITY;
    fruit.rotation += fruit.rotationSpeed;
  }

  const missed = fruits.filter((f) => !f.sliced && f.y - f.radius > canvas.height);
  if (missed.length) {
    const missedFruitCount = missed.filter((f) => !f.isBomb).length;
    if (missedFruitCount > 0) {
      lives -= missedFruitCount;
      updateHud();
      if (lives <= 0) {
        fruits = fruits.filter((f) => !missed.includes(f));
        endGame();
        return;
      }
    }
  }
  fruits = fruits.filter((f) => f.y - f.radius <= canvas.height + 60 && !(f.sliced && f.vy > 40));

  for (const p of particles) {
    p.x += p.vx;
    p.y += p.vy;
    p.vy += GRAVITY * 0.6;
    if (p.rotationSpeed) p.rotation += p.rotationSpeed;
    p.life -= p.decay;
  }
  particles = particles.filter((p) => p.life > 0);

  checkSlices();
}

function drawFingerTrail() {
  if (fingerTrail.length < 2) return;
  ctx.save();
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  for (let i = 1; i < fingerTrail.length; i++) {
    const a = fingerTrail[i - 1];
    const b = fingerTrail[i];
    const alpha = i / fingerTrail.length;
    ctx.strokeStyle = `rgba(255,255,255,${alpha})`;
    ctx.lineWidth = 6 * alpha;
    ctx.beginPath();
    ctx.moveTo(a.x, a.y);
    ctx.lineTo(b.x, b.y);
    ctx.stroke();
  }
  ctx.restore();
}

function draw() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  // Mirrored camera feed as background
  if (videoEl.readyState >= 2) {
    ctx.save();
    ctx.translate(canvas.width, 0);
    ctx.scale(-1, 1);
    ctx.globalAlpha = 0.9;
    ctx.drawImage(videoEl, 0, 0, canvas.width, canvas.height);
    ctx.globalAlpha = 1;
    ctx.restore();
  } else {
    ctx.fillStyle = "#111";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
  }

  ctx.font = "48px serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";

  for (const fruit of fruits) {
    if (fruit.sliced) continue;
    ctx.save();
    ctx.translate(fruit.x, fruit.y);
    ctx.rotate(fruit.rotation);
    ctx.font = `${fruit.radius * 1.6}px serif`;
    ctx.fillText(fruit.emoji, 0, 0);
    ctx.restore();
  }

  for (const p of particles) {
    if (p.isHalf) {
      ctx.save();
      ctx.globalAlpha = Math.max(p.life, 0);
      ctx.translate(p.x, p.y);
      ctx.rotate(p.rotation);
      ctx.font = `${p.radius * 1.6}px serif`;
      ctx.fillText(p.emoji, 0, 0);
      ctx.restore();
    } else {
      ctx.save();
      ctx.globalAlpha = Math.max(p.life, 0);
      ctx.fillStyle = p.color;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    }
  }

  drawFingerTrail();
}

function loop() {
  if (state === "playing") {
    update();
    draw();
  }
  animationHandle = requestAnimationFrame(loop);
}

function resetGame() {
  score = 0;
  lives = MAX_LIVES;
  fruits = [];
  particles = [];
  fingerTrail = [];
  lastSpawnTime = performance.now();
  updateHud();
}

function startGame() {
  resetGame();
  state = "playing";
  menuEl.classList.add("hidden");
  gameOverEl.classList.add("hidden");
}

// ---------- MediaPipe Hands setup ----------

function onHandResults(results) {
  const hasHand = results.multiHandLandmarks && results.multiHandLandmarks.length > 0;
  handStatusEl.classList.toggle("status-on", hasHand);
  handStatusEl.classList.toggle("status-off", !hasHand);

  if (!hasHand) return;

  const indexTip = results.multiHandLandmarks[0][8];
  const x = canvas.width - indexTip.x * canvas.width; // mirror to match displayed video
  const y = indexTip.y * canvas.height;

  fingerTrail.push({ x, y });
  if (fingerTrail.length > FINGER_TRAIL_LENGTH) fingerTrail.shift();
}

async function initHandTracking() {
  const hands = new Hands({
    locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/hands@0.4/${file}`,
  });
  hands.setOptions({
    maxNumHands: 1,
    modelComplexity: 0,
    minDetectionConfidence: 0.6,
    minTrackingConfidence: 0.5,
  });
  hands.onResults(onHandResults);

  const camera = new Camera(videoEl, {
    onFrame: async () => {
      await hands.send({ image: videoEl });
    },
    width: 640,
    height: 480,
  });
  await camera.start();
}

async function initCameraAndStart() {
  try {
    startBtn.disabled = true;
    startBtn.textContent = "Đang khởi động camera...";
    await initHandTracking();
    startBtn.disabled = false;
    startBtn.textContent = "Bắt đầu chơi";
    camErrorEl.textContent = "";
  } catch (err) {
    console.error(err);
    camErrorEl.textContent =
      "Không truy cập được webcam. Hãy cho phép quyền camera và chạy trang này qua http(s):// (không mở trực tiếp bằng file://).";
    startBtn.disabled = false;
    startBtn.textContent = "Thử lại";
  }
}

startBtn.addEventListener("click", async () => {
  if (videoEl.readyState < 2) {
    await initCameraAndStart();
    if (videoEl.readyState < 2) return;
  }
  startGame();
});

restartBtn.addEventListener("click", () => {
  startGame();
});

updateHud();
loop();
initCameraAndStart();
