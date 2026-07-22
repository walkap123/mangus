"""chess_coach — a chess.com coaching engine (aka "mangus").

Pipeline:
    ingest  ->  eval (Stockfish)  ->  classify moves  ->  tag  ->  coach

The store (SQLite) sits under the whole pipeline: it persists ingested games
and caches evals by FEN so no position is analyzed twice.
"""

from .models import Color, Evaluation, Game, GameResult, Player, Ply
from .ingest import ChessComClient, ChessComError, PlayerNotFound
from .store import Store
from .eval import StockfishEval, EngineNotFound, find_stockfish
from .classify import (
    MoveClass, MoveJudgment, MoveClassifier, Thresholds, win_prob, summarize,
)
from .tag import (
    Tag, Detector, HungPieceDetector, tag_game,
    static_exchange_eval, best_free_capture,
)

__all__ = [
    "ChessComClient", "ChessComError", "PlayerNotFound",
    "Game", "Ply", "Player", "Color", "GameResult", "Evaluation",
    "Store", "StockfishEval", "EngineNotFound", "find_stockfish",
    "MoveClass", "MoveJudgment", "MoveClassifier", "Thresholds",
    "win_prob", "summarize",
    "Tag", "Detector", "HungPieceDetector", "tag_game",
    "static_exchange_eval", "best_free_capture",
]

__version__ = "0.4.0"
