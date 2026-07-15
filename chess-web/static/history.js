const replayGame = new Chess();
let replayMoves = [];
let replayIndex = 0;

const replayBoard = Chessboard("replay-board", {
  pieceTheme: "pieces/{piece}.png",
  position: "start",
});

function resultLabel(result) {
  if (result === "white") return "Trắng thắng";
  if (result === "black") return "Đen thắng";
  return "Hòa";
}

async function loadGamesList() {
  const res = await fetch("/games");
  const games = await res.json();

  const tbody = document.querySelector("#games-table tbody");
  tbody.innerHTML = "";

  if (games.length === 0) {
    tbody.innerHTML = "<tr><td colspan='4'>Chưa có ván nào được lưu.</td></tr>";
    return;
  }

  games.forEach((g) => {
    const tr = document.createElement("tr");

    const timeTd = document.createElement("td");
    timeTd.textContent = g.played_at;

    const resultTd = document.createElement("td");
    resultTd.textContent = resultLabel(g.result);

    const eloTd = document.createElement("td");
    eloTd.textContent = g.elo;

    const actionTd = document.createElement("td");
    const viewBtn = document.createElement("button");
    viewBtn.textContent = "Xem lại";
    viewBtn.addEventListener("click", () => viewGame(g.id));
    actionTd.appendChild(viewBtn);

    tr.append(timeTd, resultTd, eloTd, actionTd);
    tbody.appendChild(tr);
  });
}

async function viewGame(id) {
  const res = await fetch(`/games/${id}`);
  const data = await res.json();

  replayGame.load_pgn(data.pgn);
  replayMoves = replayGame.history();
  replayGame.reset();
  replayIndex = 0;

  document.getElementById("replay-section").style.display = "block";
  renderReplay();
}

function renderReplay() {
  replayGame.reset();
  for (let i = 0; i < replayIndex; i++) {
    replayGame.move(replayMoves[i]);
  }
  replayBoard.position(replayGame.fen());
  document.getElementById("replay-move-counter").textContent =
    `Nước ${replayIndex}/${replayMoves.length}`;
}

document.getElementById("replay-prev").addEventListener("click", () => {
  if (replayIndex > 0) {
    replayIndex--;
    renderReplay();
  }
});

document.getElementById("replay-next").addEventListener("click", () => {
  if (replayIndex < replayMoves.length) {
    replayIndex++;
    renderReplay();
  }
});

loadGamesList();
