import os
import random
import sqlite3
from datetime import datetime

import chess
import chess.engine
from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__, static_folder="static", static_url_path="")

STOCKFISH_PATH = os.environ.get("STOCKFISH_PATH", "./engine/stockfish")
DB_PATH = os.environ.get("DB_PATH", "games.db")

MIN_SUPPORTED_ELO = 1320
MAX_SUPPORTED_ELO = 3190
BLUNDER_ELO_THRESHOLD = 1350
BLUNDER_CHANCE = 0.015  # 1.5%, in the 1-2% range requested


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                played_at TEXT NOT NULL,
                result TEXT NOT NULL,
                elo INTEGER NOT NULL,
                pgn TEXT NOT NULL
            )
            """
        )


init_db()


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


@app.route("/save-game", methods=["POST"])
def save_game():
    data = request.json
    with get_db() as conn:
        conn.execute(
            "INSERT INTO games (played_at, result, elo, pgn) VALUES (?, ?, ?, ?)",
            (
                datetime.now().isoformat(timespec="seconds"),
                data["result"],
                int(data["elo"]),
                data["pgn"],
            ),
        )
    return jsonify({"ok": True})


@app.route("/games", methods=["GET"])
def list_games():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, played_at, result, elo FROM games ORDER BY id DESC"
        ).fetchall()
    return jsonify([dict(row) for row in rows])


@app.route("/games/<int:game_id>", methods=["GET"])
def get_game(game_id):
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, played_at, result, elo, pgn FROM games WHERE id = ?",
            (game_id,),
        ).fetchone()
    if row is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(dict(row))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True, threaded=True)
