from typing import List
from fastapi import APIRouter, Request, Depends, HTTPException
from app.models.chess_models import MoveInput
from app.services.chess_service import (
    ChessGame,
    create_and_get_new_chess_game,
    ChessServiceError,
)
from app.utils.DIFY.voice_to_move_llm import voice_to_move, DifyServiceError
from app.services.redis.redis_setup import (
    get_redis_client,
)
from app.services.redis.redis_services import (
    redis_get_game_data_by_id,
    redis_create_new_game_id,
    redis_set_game_by_id,
    RedisServiceError,
    redis_delete_game_by_id,
)
from app.services.engine.engine_manager import EngineManager
from app.services.engine.dependencies import get_engine_manager

from app.utils.error_handling import log_error, log_success, ChessGameError, log_debug
from app.utils.DIFY.ai_analysis_llm import run_ai_analysis

chess_router = APIRouter()


@chess_router.post("/start_game/")
def start_new_game(
    request: Request,
    user_elo: int = 1320,
    engine_manager: EngineManager = Depends(get_engine_manager),
):
    """Start a new chess game."""

    redis_client = request.app.state.redis_client
    if not redis_client:
        log_error("Redis Connection Failed")
        raise HTTPException(status_code=500, detail="Redis Connection Failed")

    # Create a new redis state and get the unique game id
    try:
        game_id = redis_create_new_game_id(redis_client=redis_client)
        # now we create a new ChessGame instance
        game: ChessGame = create_and_get_new_chess_game(
            game_id=game_id, elo_level=user_elo, engine_manager=engine_manager
        )
        # now we insert this in redis
        redis_set_game_by_id(
            game_id=game_id, redis_client=redis_client, data=game.to_dict()
        )
        # game.reset()
        return {
            "message": "New game started",
            "board_fen": game.get_fen(),
            "game_id": game_id,
            "StockFish_Elo": user_elo,
        }

    except RedisServiceError as e:
        log_error(f"Redis operation failed:{str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

    except Exception as e:
        log_error(f"Failed to start game: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to start new game: {str(e)}"
        )


@chess_router.post("/play_move/")
async def play_user_move(
    move_input: MoveInput,
    request: Request,
    game_id: str,
    engine_manager: EngineManager = Depends(get_engine_manager),
):
    """Handles user move and gets Stockfish's response."""

    try:
        redis_client = request.app.state.redis_client
        if not redis_client:
            log_error("Redis Connection Failed")
            raise HTTPException(status_code=500, detail="Redis Connection Failed")

        game_data = redis_get_game_data_by_id(
            game_id=game_id, redis_client=redis_client
        )

        log_success(f"Game data from reds for id {game_id}: {game_data} ")
        # reconstruct game instance using the game_data
        game = ChessGame.from_dict(game_data, engine_manager=engine_manager)
        log_success(f"Game after recreation:{game}")
        # make move
        game.make_user_move(move_input.move)

        stockfish_move, stockfish_move_san, is_game_over = await game.get_engine_move()

        if not stockfish_move or not stockfish_move_san:
            # Game over after user move
            game.quit_game(engine_manager=engine_manager)
            redis_delete_game_by_id(game_id=game_id, redis_client=redis_client)
            return {
                "message": "Game Over after user Move",
                "user_move": move_input.move,
                "stockfish_move": None,
                "stockfish_san": None,
                "board_fen": game.get_fen(),
                "game_id": game.game_id,
                "is_game_over": True,
                "winner": "User",
            }

        if is_game_over:
            # Game over after engine move
            game.quit_game(engine_manager=engine_manager)
            redis_delete_game_by_id(game_id=game_id, redis_client=redis_client)
            return {
                "message": "Game Over after Engine Move",
                "user_move": move_input.move,
                "stockfish_move": stockfish_move,
                "stockfish_san": stockfish_move_san,
                "board_fen": game.get_fen(),
                "game_id": game.game_id,
                "is_game_over": True,
                "winner": "Computer",
            }

        # Now update back in redis
        redis_set_game_by_id(
            game_id=game_id, redis_client=redis_client, data=game.to_dict()
        )
        log_success(f"Game state updated in redis")

        return {
            "message": "Move played",
            "user_move": move_input.move,
            "stockfish_move": stockfish_move,
            "stockfish_san": stockfish_move_san,
            "board_fen": game.get_fen(),
            "game_id": game.game_id,
            "is_game_over": False,
        }
    except RedisServiceError as e:
        log_error(f"Redis operation failed:{str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except ValueError as v:
        raise HTTPException(status_code=400, detail=f"Invalid or illegal move {v}")
    except Exception as e:
        log_error(f"Failed to play move: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to play move: {e}")


@chess_router.post("/end_game/")
def end_game(
    request: Request,
    game_id: str,
    engine_manager: EngineManager = Depends(get_engine_manager),
):
    """Ends the game and stops the engine."""

    try:
        redis_client = request.app.state.redis_client
        if not redis_client:
            log_error("Redis Connection Failed")
            raise HTTPException(status_code=500, detail="Redis Connection Failed")

        game_data = redis_get_game_data_by_id(
            game_id=game_id, redis_client=redis_client
        )

        log_success(
            f"Game data from redis before playing user_move for id {game_id}: {game_data} "
        )
        # reconstruct game instance using the game_data
        game = ChessGame.from_dict(game_data, engine_manager=engine_manager)
        log_success(f"Game after recreation:{game}")

        game.quit_game(engine_manager=engine_manager)

        # delete game from redis
        message = redis_delete_game_by_id(game_id=game_id, redis_client=redis_client)
        return {"message": message}

    except RedisServiceError as re:
        raise HTTPException(status_code=500, detail=str(re))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error ending game:{e}")


@chess_router.post("/undo_move/")
def undo_move(
    request: Request,
    game_id: str,
    engine_manager: EngineManager = Depends(get_engine_manager),
):
    """Undo the last move."""
    try:
        redis_client = request.app.state.redis_client
        if not redis_client:
            log_error("Redis Connection Failed")
            raise HTTPException(status_code=500, detail="Redis Connection Failed")

        game_data = redis_get_game_data_by_id(
            game_id=game_id, redis_client=redis_client
        )

        log_success(f"Game data from reds for id {game_id}: {game_data} ")
        # reconstruct game instance using the game_data
        game = ChessGame.from_dict(game_data, engine_manager=engine_manager)
        log_success(f"Game after recreation:{game}")

        fen_after_undo = game.undo_move()

        # Now also update redis

        redis_set_game_by_id(
            game_id=game_id, redis_client=redis_client, data=game.to_dict()
        )
        log_success(f"Game state updated in redis after takeback")

        return {
            "message": "Move undone",
            "board_fen_after_undo": fen_after_undo,
            "game_id": game_id,
        }
    except RedisServiceError as re:
        log_error(f"Redis operation failed: {str(re)}")
        raise HTTPException(status_code=500, detail=str(re))
    except ChessServiceError as c:
        log_error(f"Chess service error: {str(c)}")
        raise HTTPException(status_code=500, detail=str(c))


@chess_router.get("/get_ai_analysis")
async def get_ai_analysis(
    game_id: str,
    request: Request,
    engine_manager: EngineManager = Depends(get_engine_manager),
):
    """Gets Analysis from DIFY Workflow"""

    try:
        redis_client = request.app.state.redis_client
        if not redis_client:
            log_error("Redis Connection Failed")
            raise HTTPException(status_code=500, detail="Redis Connection Failed")

        game_data = redis_get_game_data_by_id(
            game_id=game_id, redis_client=redis_client
        )

        log_success(f"Game data from reds for id {game_id}: {game_data} ")
        # reconstruct game instance using the game_data
        game = ChessGame.from_dict(game_data, engine_manager=engine_manager)
        log_success(f"Game after recreation:{game}")

        # First get top moves:
        top_moves: List = await game.get_top_stockfish_moves()
        fen = game.get_fen()
        turn = game.board.turn
        log_debug(f"Top Moves from stockfish = {top_moves}")
        analysis = run_ai_analysis(str(top_moves), fen, turn)

        return {
            "game_id": game_id,
            "fen": fen,
            "top_moves": top_moves,
            "analysis": analysis,
        }
    except Exception as e:
        log_error(f"Error while generating Analysis from dify:{e}")
        raise HTTPException(
            status_code=500, detail=f"Error while generating Analysis from dify:{e}"
        )


@chess_router.get("/get_top_moves")
async def get_top_moves(
    game_id: str,
    request: Request,
    engine_manager: EngineManager = Depends(get_engine_manager),
):
    """Gets Maximum of 3 top moves at the position"""
    try:
        redis_client = request.app.state.redis_client
        if not redis_client:
            log_error("Redis Connection Failed")
            raise HTTPException(status_code=500, detail="Redis Connection Failed")

        game_data = redis_get_game_data_by_id(
            game_id=game_id, redis_client=redis_client
        )

        log_success(f"Game data from reds for id {game_id}: {game_data} ")
        # reconstruct game instance using the game_data
        game = ChessGame.from_dict(game_data, engine_manager=engine_manager)
        log_success(f"Game after recreation:{game}")

        top_moves: List = await game.get_top_stockfish_moves()

        return {game_id: game_id, "top_moves": top_moves, "fen": game.get_fen()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching top moves:{e}")


@chess_router.post("/voice_to_move_san/")
def voice_to_move_san(
    user_input: str,
    request: Request,
    game_id: str,
    engine_manager: EngineManager = Depends(get_engine_manager),
):
    """Converts voice input to move in SAN format using LLM and current fen position."""
    try:
        redis_client = request.app.state.redis_client
        if not redis_client:
            log_error("Redis Connection Failed")
            raise HTTPException(status_code=500, detail="Redis Connection Failed")

        game_data = redis_get_game_data_by_id(
            game_id=game_id, redis_client=redis_client
        )

        log_success(f"Game data from reds for id {game_id}: {game_data} ")
        # reconstruct game instance using the game_data
        game = ChessGame.from_dict(game_data, engine_manager=engine_manager)
        log_success(f"Game after recreation:{game}")

        # Get current FEN
        current_fen = game.get_fen()
        response = voice_to_move(user_input, current_fen)
        return {"message": response.strip()}

    except RedisServiceError as re:
        log_error(f"Redis operation failed: {str(re)}")
        raise HTTPException(status_code=500, detail=str(re))
    except ChessServiceError as c:
        log_error(f"Chess service error: {str(c)}")
        raise HTTPException(status_code=500, detail=str(c))
    except DifyServiceError as d:
        log_error(f"Error while converting move to SAN: {d}")
        raise HTTPException(
            status_code=500, detail=f"Error while converting move to SAN: {d}"
        )
