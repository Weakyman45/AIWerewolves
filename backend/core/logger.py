
import json
import os
from datetime import datetime
from pydantic import BaseModel


class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, BaseModel):
            return obj.model_dump()
        return super().default(obj)


class GameLogger:
    def __init__(self, log_dir="./logs"):
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)

    def _get_log_path(self, game_id):
        return os.path.join(self.log_dir, f"game_{game_id}.jsonl")

    def log_game_start(self, game_state):
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "game_start",
            "game_state": game_state.model_dump()
        }
        self._append_log(game_state.game_id, log_entry)

    def log_phase_change(self, game_id, round_number, phase):
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "phase_change",
            "round_number": round_number,
            "phase": phase
        }
        self._append_log(game_id, log_entry)

    def log_agent_decision(self, game_id, player_id, decision):
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "agent_decision",
            "player_id": player_id,
            "decision": decision.model_dump()
        }
        self._append_log(game_id, log_entry)

    def log_night_action(self, game_id, action):
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "night_action",
            "action": action
        }
        self._append_log(game_id, log_entry)

    def log_vote(self, game_id, vote):
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "vote",
            "vote": vote
        }
        self._append_log(game_id, log_entry)

    def log_death(self, game_id, player_id, cause):
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "death",
            "player_id": player_id,
            "cause": cause
        }
        self._append_log(game_id, log_entry)

    def log_game_end(self, game_state):
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "game_end",
            "winner": game_state.winner.value if game_state.winner else None,
            "game_state": game_state.model_dump()
        }
        self._append_log(game_state.game_id, log_entry)

    def _append_log(self, game_id, log_entry):
        log_path = self._get_log_path(game_id)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False, cls=CustomJSONEncoder) + "\n")

    def load_game_logs(self, game_id):
        log_path = self._get_log_path(game_id)
        if not os.path.exists(log_path):
            return []
        with open(log_path, "r", encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]

