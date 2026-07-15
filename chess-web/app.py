import os
import random

import chess
import chess.engine
from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__, static_folder="static", static_url_path="")

STOCKFISH_PATH = os.environ.get("STOCKFISH_PATH", "./engine/stockfish")

MIN_SUPPORTED_ELO = 1320
MAX_SUPPORTED_ELO = 3190
BLUNDER_ELO_THRESHOLD = 1350
BLUNDER_CHANCE = 0.015  # 1.5%, in the 1-2% range requested


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/bot-move", methods=["POST"])
def bot_move():
    data = request.json
    fen = data["fen"]
    elo = int(data.get("elo", 1500))

    board = chess.Board(fen)

    if elo <= BLUNDER_ELO_THRESHOLD and random.random() < BLUNDER_CHANCE:
        move = random.choice(list(board.legal_moves))
        return jsonify({"move": move.uci(), "blunder": True})

    clamped_elo = max(MIN_SUPPORTED_ELO, min(elo, MAX_SUPPORTED_ELO))
    with chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH) as engine:
        engine.configure({"UCI_LimitStrength": True, "UCI_Elo": clamped_elo})
        result = engine.play(board, chess.engine.Limit(time=1.0))

    return jsonify({"move": result.move.uci(), "blunder": False})


if __name__ == "__main__":
    app.run(port=5000, debug=True)
