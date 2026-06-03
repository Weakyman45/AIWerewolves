
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import asyncio
import json
import os

from backend.engine.game import WerewolfGame
from backend.core.logger import GameLogger

router = APIRouter(prefix="/api", tags=["game"])

active_games: dict = {}


class StartGameRequest(BaseModel):
    player_names: List[str]


class GameStatusResponse(BaseModel):
    game_id: str
    status: str
    winner: Optional[str] = None
    players: List[dict]
    current_round: int
    current_phase: str
    error: Optional[str] = None
    is_paused: bool = False


@router.post("/game/start")
async def start_game(request: StartGameRequest):
    print(f"Creating game with {len(request.player_names)} players: {request.player_names}")
    logger = GameLogger()
    game = WerewolfGame(request.player_names, logger)
    print(f"Game created with id: {game.game_id}")
    active_games[game.game_id] = {
        "game": game,
        "task": None,
        "status": "ready"
    }
    print(f"Game added to active_games, total games: {len(active_games)}")
    return {
        "game_id": game.game_id,
        "message": "Game created"
    }


@router.post("/game/{game_id}/run")
async def run_game(game_id: str):
    if game_id not in active_games:
        raise HTTPException(status_code=404, detail="Game not found")
    
    game_data = active_games[game_id]
    game = game_data["game"]
    
    async def run_and_update():
        try:
            game_data["status"] = "running"
            print("Starting game...")
            winner = await game.run()
            print(f"Game finished, winner: {winner}")
            game_data["status"] = "finished"
            game_data["winner"] = winner.value
        except Exception as e:
            print(f"Error in game: {e}")
            import traceback
            print(f"Stack trace: {traceback.format_exc()}")
            game_data["status"] = "error"
            game_data["error"] = str(e)
    
    task = asyncio.create_task(run_and_update())
    game_data["task"] = task
    
    return {
        "game_id": game_id,
        "message": "Game started"
    }


@router.post("/game/{game_id}/pause")
async def pause_game(game_id: str):
    if game_id not in active_games:
        raise HTTPException(status_code=404, detail="Game not found")
    
    game_data = active_games[game_id]
    game = game_data["game"]
    game.pause()
    game_data["status"] = "paused"
    
    return {
        "game_id": game_id,
        "message": "Game paused"
    }


@router.post("/game/{game_id}/resume")
async def resume_game(game_id: str):
    if game_id not in active_games:
        raise HTTPException(status_code=404, detail="Game not found")
    
    game_data = active_games[game_id]
    game = game_data["game"]
    game.resume()
    game_data["status"] = "running"
    
    return {
        "game_id": game_id,
        "message": "Game resumed"
    }


@router.get("/game/{game_id}/status")
async def get_game_status(game_id: str):
    print(f"Getting status for game: {game_id}")
    print(f"Active games: {list(active_games.keys())}")
    if game_id not in active_games:
        print(f"Game not found: {game_id}")
        raise HTTPException(status_code=404, detail="Game not found")
    
    game_data = active_games[game_id]
    game = game_data["game"]
    print(f"Game status: {game_data['status']}")
    
    players = []
    for pid, ps in game.player_states.items():
        players.append({
            "id": pid,
            "name": ps.name,
            "role": ps.role.value,
            "is_alive": ps.is_alive
        })
    print(f"Players: {players}")
    
    result = GameStatusResponse(
        game_id=game_id,
        status=game_data["status"],
        winner=game_data.get("winner"),
        players=players,
        current_round=game.state.current_round,
        current_phase=game.state.current_phase.value,
        error=game_data.get("error"),
        is_paused=game.is_paused
    )
    print(f"Returning status: {result}")
    return result


@router.get("/game/{game_id}/logs")
async def get_game_logs(game_id: str):
    log_path = f"logs/game_{game_id}.jsonl"
    if not os.path.exists(log_path):
        return {"logs": []}
    
    logs = []
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                logs.append(json.loads(line))
    
    return {"logs": logs}


@router.get("/games")
async def list_games():
    return {
        "games": list(active_games.keys())
    }

