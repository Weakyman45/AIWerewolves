import json
import os
from typing import Dict, List, Any, Optional
from datetime import datetime
from backend.core.config import settings


class LogParser:
    def __init__(self, log_dir: Optional[str] = None):
        self.log_dir = log_dir or settings.LOG_DIR

    def parse_game(self, game_id: str) -> Optional[Dict[str, Any]]:
        log_path = os.path.join(self.log_dir, f"game_{game_id}.jsonl")
        if not os.path.exists(log_path):
            return None
        return self._parse_file(log_path)

    def parse_all_games(self) -> List[Dict[str, Any]]:
        games = []
        if not os.path.exists(self.log_dir):
            return games
        for filename in os.listdir(self.log_dir):
            if filename.startswith("game_") and filename.endswith(".jsonl"):
                game_id = filename.replace("game_", "").replace(".jsonl", "")
                game_data = self.parse_game(game_id)
                if game_data:
                    games.append(game_data)
        return games

    def _parse_file(self, log_path: str) -> Optional[Dict[str, Any]]:
        events = []
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        events.append(json.loads(line))
        except Exception:
            return None

        if not events:
            return None

        return self._structure_game_data(events)

    def _structure_game_data(self, events: List[Dict]) -> Dict[str, Any]:
        game_id = self._extract_game_id(events)
        winner = self._extract_winner(events)
        players = self._extract_players(events)
        rounds = self._extract_rounds(events)
        metrics = self._calculate_metrics(events, players, winner)

        return {
            "game_id": game_id,
            "winner": winner,
            "players": players,
            "rounds": rounds,
            "metrics": metrics,
            "raw_events": events,
        }

    def _extract_game_id(self, events: List[Dict]) -> str:
        for event in events:
            if event.get("type") == "game_start":
                return event.get("game_state", {}).get("game_id", "unknown")
        return "unknown"

    def _extract_winner(self, events: List[Dict]) -> Optional[str]:
        for event in events:
            if event.get("type") == "game_end":
                return event.get("winner")
        return None

    def _extract_players(self, events: List[Dict]) -> Dict[str, Any]:
        players = {}
        for event in events:
            if event.get("type") == "game_start":
                players_data = event.get("game_state", {}).get("players", {})
                for pid, p in players_data.items():
                    players[pid] = {
                        "player_id": pid,
                        "name": p.get("name"),
                        "role": p.get("role"),
                        "team": self._role_to_team(p.get("role")),
                        "is_alive": True
                    }
                break
        return players

    def _role_to_team(self, role: Optional[str]) -> str:
        if role == "werewolf":
            return "werewolves"
        return "villagers"

    def _extract_rounds(self, events: List[Dict]) -> List[Dict[str, Any]]:
        rounds = []
        current_round = 1
        round_events = []

        for event in events:
            if event.get("type") == "phase_change" and event.get("phase") == "夜晚":
                if round_events:
                    rounds.append({
                        "round_number": current_round,
                        "events": round_events
                    })
                    current_round += 1
                    round_events = []
            round_events.append(event)

        if round_events:
            rounds.append({
                "round_number": current_round,
                "events": round_events
            })

        return rounds

    def _calculate_metrics(self, events: List[Dict], players: Dict, winner: Optional[str]) -> Dict[str, Any]:
        metrics = {
            "werewolf_win": winner == "werewolves",
            "villager_win": winner == "villagers",
            "duration_rounds": self._count_rounds(events),
            "key_moments": self._find_key_moments(events),
            "first_night_kill": self._find_first_night_kill(events),
            "first_check": self._find_first_check(events),
            "sheriff_elected": self._sheriff_elected(events),
        }
        return metrics

    def _count_rounds(self, events: List[Dict]) -> int:
        round_count = 0
        for event in events:
            if event.get("type") == "phase_change" and event.get("phase") == "夜晚":
                round_count += 1
        return max(round_count, 1)

    def _find_key_moments(self, events: List[Dict]) -> List[Dict]:
        key_moments = []
        for event in events:
            if event.get("type") in ["death", "sheriff_elected", "vote_result", "game_end"]:
                key_moments.append(event)
        return key_moments

    def _find_first_night_kill(self, events: List[Dict]) -> Optional[Dict]:
        for event in events:
            if event.get("type") == "night_action":
                action = event.get("action", {})
                if action.get("action") == "kill":
                    return action
        return None

    def _find_first_check(self, events: List[Dict]) -> Optional[Dict]:
        for event in events:
            if event.get("type") == "night_action":
                action = event.get("action", {})
                if action.get("action") == "check":
                    return action
        return None

    def _sheriff_elected(self, events: List[Dict]) -> bool:
        for event in events:
            if event.get("type") == "sheriff_elected":
                return True
        return False
