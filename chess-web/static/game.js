const game = new Chess();
const statusEl = document.getElementById("status");
const eloInput = document.getElementById("elo");
const eloValue = document.getElementById("eloValue");

eloInput.addEventListener("input", () => {
  eloValue.textContent = eloInput.value;
});

const board = Chessboard("board", {
  draggable: true,
  position: "start",
  onDrop: handleMove,
});

function handleMove(source, target) {
  const move = game.move({ from: source, to: target, promotion: "q" });
  if (move === null) return "snapback";

  updateStatus();
  if (!game.game_over()) {
    window.setTimeout(botMove, 250);
  }
}

async function botMove() {
  statusEl.textContent = "Bot đang suy nghĩ...";

  const res = await fetch("/bot-move", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ fen: game.fen(), elo: Number(eloInput.value) }),
  });
  const data = await res.json();

  game.move({
    from: data.move.slice(0, 2),
    to: data.move.slice(2, 4),
    promotion: data.move[4],
  });
  board.position(game.fen());
  updateStatus(data.blunder);
}

function updateStatus(botBlundered) {
  if (game.in_checkmate()) {
    statusEl.textContent = "Chiếu bí! " + (game.turn() === "w" ? "Đen" : "Trắng") + " thắng.";
    return;
  }
  if (game.in_draw()) {
    statusEl.textContent = "Hòa cờ.";
    return;
  }
  statusEl.textContent = botBlundered ? "Bot vừa đi hớ (blunder)!" : "Tới lượt " + (game.turn() === "w" ? "Trắng" : "Đen");
}

document.getElementById("resetBtn").addEventListener("click", () => {
  game.reset();
  board.position("start");
  statusEl.textContent = "";
});
