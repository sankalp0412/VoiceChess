from fastapi import APIRouter, Depends, HTTPException
from app.models.chess_models import MoveInput
from app.services.chess_service import ChessGame, get_chess_game

chess_router = APIRouter()

@chess_router.post("/start_game/")
def start_new_game(game: ChessGame = Depends(get_chess_game), user_elo: int = 1200):
    """Start a new chess game."""
    game.reset()
    game.setup_stockfish_elo(user_elo)
    return {"message": "New game started", "board_fen": game.get_fen(), "StockFish_Elo": game.stockfish_engine.get_parameters()["UCI_Elo"]}

@chess_router.post("/play_move/")
def play_user_move(move_input: MoveInput, game: ChessGame = Depends(get_chess_game)):
    """Handles user move and gets Stockfish's response."""
    try:
        game.make_user_move(move_input.move)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid or illegal move")

    if game.is_game_over():
        return {"message": "Game over!", "result": game.board.result()}

    stockfish_move = game.get_engine_move()
    
    return {
        "message": "Move played",
        "user_move": move_input.move,
        "stockfish_move": stockfish_move,
        "board_fen": game.get_fen()
    }

@chess_router.post("/end_game/")
def end_game(game: ChessGame = Depends(get_chess_game)):
    """Ends the game and stops the engine."""
    game.quit_engine()
    return {"message": "Game ended."}