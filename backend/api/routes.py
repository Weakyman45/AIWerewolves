
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Any
import asyncio
import json
import os
from datetime import datetime

from backend.engine.game import WerewolfGame
from backend.core.logger import GameLogger
from backend.evolution.version_control import VersionControl
from backend.evolution.controller import EvolutionController

router = APIRouter(prefix="/api", tags=["game"])

active_games: dict = {}
evolution_state: dict[str, Any] = {
    "task": None,
    "status": "idle",
    "latest_result": None,
    "history": [],
    "error": None,
}


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
    strategy_version: Optional[str] = None


class EvolutionRunRequest(BaseModel):
    iterations: int = 1
    train_games: int = 1
    ab_games: int = 4
    game_runner: str = "mock"
    win_rate_threshold: float = 0.0
    trigger_game_id: Optional[str] = None


def _version_summary(version_control: VersionControl, version: str) -> dict:
    metadata = version_control.get_metadata(version) or {}
    stats = version_control.get_stats(version) or {}
    metrics = stats.get("metrics", {})
    analysis = metadata.get("analysis_summary", {})
    training = metadata.get("training_summary", {})
    changes = metadata.get("changes", [])

    return {
        "version": version,
        "parent": metadata.get("parent"),
        "created_at": metadata.get("created_at"),
        "status": metadata.get("status"),
        "accepted": metadata.get("accepted"),
        "focus": metadata.get("focus"),
        "candidate_from": metadata.get("candidate_from"),
        "validated_at": metadata.get("validated_at"),
        "improvement": metadata.get("improvement"),
        "promotion_summary": metadata.get("promotion_summary"),
        "ab_result": metadata.get("ab_result"),
        "test_games": metadata.get("test_games", metrics.get("total_games", 0)),
        "win_rate": metadata.get("win_rate", {}),
        "metrics": metrics,
        "analysis_summary": {
            "total_games": analysis.get("total_games", 0),
            "werewolf_win_rate": analysis.get("werewolf_win_rate", 0),
            "villager_win_rate": analysis.get("villager_win_rate", 0),
            "average_rounds": analysis.get("average_rounds", 0),
            "quality_metrics": analysis.get("quality_metrics", {}),
        },
        "training_summary": training,
        "changes": changes[:8],
    }


def _build_rubric_summary(
    status: str,
    active_run: Optional[dict],
    current_summary: Optional[dict],
    summaries: list[dict],
    version_count: int,
) -> dict:
    latest_ab_version = next(
        (
            version for version in reversed(summaries)
            if version.get("ab_result")
        ),
        None,
    )
    latest_ab_result = latest_ab_version.get("ab_result") if latest_ab_version else None
    current_ab_result = current_summary.get("ab_result") if current_summary else None
    current_promoted_by_ab = bool(
        current_summary
        and current_summary.get("accepted") is True
        and current_ab_result
        and not current_ab_result.get("skipped")
    )

    training = current_summary.get("training_summary", {}) if current_summary else {}
    quality = (
        (current_summary.get("analysis_summary", {}) if current_summary else {})
        .get("quality_metrics", {})
        .get("counts", {})
    )
    completed = training.get("completed", 0)
    timed_out = training.get("timed_out", 0)
    failed = training.get("failed", 0)
    loop_stage = (
        active_run.get("phase")
        if status == "running" and active_run
        else "ab_validated"
        if latest_ab_result
        else "version_ready"
        if version_count > 0
        else "not_initialized"
    )

    return {
        "loop_stage": loop_stage,
        "latest_ab_result": latest_ab_result,
        "latest_ab_version": latest_ab_version.get("version") if latest_ab_version else None,
        "current_promoted_by_ab": current_promoted_by_ab,
        "rollback_version_count": max(0, version_count - 1),
        "training_health": {
            "completed": completed,
            "timed_out": timed_out,
            "failed": failed,
            "has_runtime_issues": timed_out > 0 or failed > 0,
        },
        "bad_case_summary": {
            "nonseer_claim_repairs": quality.get("nonseer_claim_repairs", 0),
            "llm_fallbacks": quality.get("llm_fallbacks", 0),
            "unauthorized_werewolf_fake_seer_blocks": quality.get("unauthorized_werewolf_fake_seer_blocks", 0),
            "public_claim_consistency_repairs": quality.get("public_claim_consistency_repairs", 0),
        },
    }


def _build_evolution_status() -> dict:
    version_control = VersionControl()
    versions = version_control.list_versions()
    latest_pointer = version_control.get_latest_pointer()
    current = latest_pointer or (versions[-1] if versions else None)
    summary_versions = list(versions[-8:])
    if current and current not in summary_versions:
        summary_versions.insert(0, current)
    summaries = [_version_summary(version_control, version) for version in summary_versions]
    evolved_version_count = 0
    for version in versions:
        metadata = version_control.get_metadata(version) or {}
        if metadata.get("parent") or metadata.get("changes"):
            evolved_version_count += 1
    current_summary = _version_summary(version_control, current) if current else None

    return {
        "status": evolution_state["status"],
        "is_running": evolution_state["status"] == "running",
        "current_version": current,
        "latest_pointer": latest_pointer,
        "version_count": len(versions),
        "versions": summaries,
        "current": current_summary,
        "evolved_version_count": evolved_version_count,
        "latest_result": evolution_state.get("latest_result"),
        "history": evolution_state.get("history", [])[-5:],
        "active_run": evolution_state.get("active_run"),
        "error": evolution_state.get("error"),
        "rubric_summary": _build_rubric_summary(
            evolution_state["status"],
            evolution_state.get("active_run"),
            current_summary,
            summaries,
            len(versions),
        ),
    }


def _load_latest_strategy_prompts() -> tuple[dict, Optional[str]]:
    version_control = VersionControl()
    version = version_control.get_latest_pointer() or version_control.get_latest_version()
    if not version or not version_control.version_exists(version):
        return {}, None

    prompts = {}
    for role in ["werewolf", "seer", "witch", "hunter", "villager"]:
        prompt = version_control.get_prompt(version, role)
        if prompt:
            prompts[role] = prompt
    return prompts, version


@router.post("/game/start")
async def start_game(request: StartGameRequest):
    print(f"Creating game with {len(request.player_names)} players: {request.player_names}")
    logger = GameLogger()
    strategy_prompts, strategy_version = _load_latest_strategy_prompts()
    game = WerewolfGame(request.player_names, logger, strategy_prompts=strategy_prompts)
    print(f"Game created with id: {game.game_id}")
    if strategy_version:
        print(f"Loaded strategy version for frontend game: {strategy_version}")
    active_games[game.game_id] = {
        "game": game,
        "task": None,
        "status": "ready",
        "strategy_version": strategy_version,
    }
    print(f"Game added to active_games, total games: {len(active_games)}")
    return {
        "game_id": game.game_id,
        "message": "Game created",
        "strategy_version": strategy_version,
    }


@router.post("/game/{game_id}/run")
async def run_game(game_id: str):
    if game_id not in active_games:
        raise HTTPException(status_code=404, detail="Game not found")
    
    game_data = active_games[game_id]
    game = game_data["game"]
    existing_task = game_data.get("task")
    if game_data.get("status") == "running" or (existing_task and not existing_task.done()):
        return {
            "game_id": game_id,
            "message": "Game already running",
            "status": game_data.get("status", "running"),
        }
    if game_data.get("status") == "finished":
        return {
            "game_id": game_id,
            "message": "Game already finished",
            "status": "finished",
        }
    if game_data.get("status") == "error":
        raise HTTPException(status_code=409, detail="Game is in error state")

    game_data["status"] = "running"

    async def run_and_update():
        try:
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
            "is_alive": ps.is_alive,
            "is_sheriff": ps.is_sheriff,
            "in_sheriff_election": ps.in_sheriff_election,
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
        is_paused=game.is_paused,
        strategy_version=game_data.get("strategy_version"),
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


@router.get("/evolution/status")
async def get_evolution_status():
    return _build_evolution_status()


@router.get("/evolution/history")
async def get_evolution_history():
    return {
        "history": evolution_state.get("history", []),
        "latest_result": evolution_state.get("latest_result"),
    }


@router.get("/evolution/timeline")
async def get_evolution_timeline():
    version_control = VersionControl()
    versions = version_control.list_versions()
    latest_pointer = version_control.get_latest_pointer()
    return {
        "latest_pointer": latest_pointer,
        "versions": [_version_summary(version_control, version) for version in versions],
    }


@router.post("/evolution/run")
async def run_evolution(request: EvolutionRunRequest):
    if evolution_state["status"] == "running":
        raise HTTPException(status_code=409, detail="Evolution is already running")

    version_control = VersionControl()
    initial_version = version_control.get_latest_pointer() or version_control.get_latest_version()
    game_runner = request.game_runner if request.game_runner in {"mock", "live", "live-fast"} else "mock"
    controller = EvolutionController(
        initial_version=initial_version,
        num_games_per_iteration=max(1, request.train_games),
        ab_games=max(1, request.ab_games),
        win_rate_threshold=max(0.0, request.win_rate_threshold),
        fallback_only=True,
        game_runner=game_runner,
    )
    controller.initialize()

    def progress_callback(iteration: int, total: int, phase: str, result: Optional[dict] = None):
        evolution_state["active_run"] = {
            "iteration": iteration,
            "total_iterations": total,
            "phase": phase,
            "initial_version": initial_version,
            "trigger_game_id": request.trigger_game_id,
            "train_games": max(1, request.train_games),
            "ab_games": max(1, request.ab_games),
            "game_runner": game_runner,
            "latest_iteration_result": result,
        }

    async def run_and_update():
        try:
            evolution_state["status"] = "running"
            evolution_state["error"] = None
            evolution_state["active_run"] = {
                "iteration": 0,
                "total_iterations": max(1, request.iterations),
                "phase": "queued",
                "initial_version": initial_version,
                "trigger_game_id": request.trigger_game_id,
                "train_games": max(1, request.train_games),
                "ab_games": max(1, request.ab_games),
                "game_runner": game_runner,
            }
            result = await controller.start_evolution(
                max_iterations=max(1, request.iterations),
                progress_callback=progress_callback,
            )
            evolution_state["status"] = "finished"
            evolution_state["latest_result"] = result
            evolution_state["history"].append({
                "timestamp": result["history"][-1]["timestamp"] if result.get("history") else None,
                "initial_version": initial_version,
                "final_version": result.get("final_version"),
                "total_iterations": result.get("total_iterations"),
                "trigger_game_id": request.trigger_game_id,
                "result": result,
            })
        except Exception as error:
            evolution_state["status"] = "error"
            evolution_state["error"] = f"{type(error).__name__}: {error}"
        finally:
            evolution_state["task"] = None

    evolution_state["status"] = "running"
    evolution_state["task"] = asyncio.create_task(run_and_update())

    return {
        "message": "Evolution started",
        "initial_version": initial_version,
        "iterations": max(1, request.iterations),
        "runner": game_runner,
        "fallback_only": True,
        "trigger_game_id": request.trigger_game_id,
    }


@router.post("/evolution/rollback/{version}")
async def rollback_evolution_version(version: str):
    if evolution_state["status"] == "running":
        raise HTTPException(status_code=409, detail="Cannot rollback while evolution is running")

    version_control = VersionControl()
    if not version_control.version_exists(version):
        raise HTTPException(status_code=404, detail="Version not found")

    previous = version_control.get_latest_pointer()
    version_control.rollback(version)
    metadata = version_control.get_metadata(version) or {}
    metadata["status"] = "accepted"
    metadata["accepted"] = True
    metadata["rollback_promoted_at"] = metadata.get("rollback_promoted_at") or []
    metadata["rollback_promoted_at"].append({
        "timestamp": datetime.now().isoformat(),
        "previous_latest": previous,
    })
    version_control.update_metadata(version, metadata)

    evolution_state["history"].append({
        "timestamp": metadata["rollback_promoted_at"][-1]["timestamp"],
        "initial_version": previous,
        "final_version": version,
        "total_iterations": 0,
        "trigger_game_id": None,
        "result": {
            "success": True,
            "manual_rollback": True,
            "old_version": previous,
            "final_version": version,
        },
    })

    return {
        "message": "Rollback complete",
        "previous_version": previous,
        "current_version": version,
    }
