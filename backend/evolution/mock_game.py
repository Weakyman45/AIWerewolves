import hashlib
import uuid
from datetime import datetime
from typing import List, Optional

from backend.core.logger import GameLogger
from backend.core.models import GamePhase, GameState, PlayerState, Role, Team


class MockGameRunner:
    def __init__(
        self,
        player_names: List[str],
        logger: Optional[GameLogger] = None,
        seed_key: str = "mock",
        werewolf_version: Optional[str] = None,
        other_version: Optional[str] = None,
    ):
        self.player_names = player_names
        self.logger = logger or GameLogger()
        self.seed_key = seed_key
        self.werewolf_version = werewolf_version or "mock"
        self.other_version = other_version or self.werewolf_version
        self.game_id = str(uuid.uuid4())
        self.state = self._build_initial_state()

    async def run(self) -> Team:
        winner = self._determine_winner()
        self.logger.log_game_start(self.state)
        self.logger.log_phase_change(self.game_id, 1, "夜晚")

        if winner == Team.WEREWOLVES:
            self._log_werewolf_win_script()
        else:
            self._log_villager_win_script()

        self.state.winner = winner
        self.state.current_phase = GamePhase.GAME_OVER
        self.state.ended_at = datetime.now()
        self.logger.log_game_end(self.state)
        return winner

    def _build_initial_state(self) -> GameState:
        roles = [
            Role.WEREWOLF,
            Role.WEREWOLF,
            Role.SEER,
            Role.WITCH,
            Role.HUNTER,
            Role.VILLAGER,
        ]
        players = {}
        for index, role in enumerate(roles):
            name = self.player_names[index] if index < len(self.player_names) else f"Player {index + 1}"
            player_id = f"player_{index}"
            players[player_id] = PlayerState(
                player_id=player_id,
                name=name,
                role=role,
                is_alive=True,
            )
        return GameState(
            game_id=self.game_id,
            players=players,
            current_phase=GamePhase.NIGHT,
            current_round=1,
        )

    def _determine_winner(self) -> Team:
        werewolf_strength = self._version_strength(self.werewolf_version)
        villager_strength = self._version_strength(self.other_version)
        threshold = 0.5 + max(-0.25, min(0.25, (werewolf_strength - villager_strength) * 0.08))
        score = self._stable_score(
            f"{self.seed_key}:{self.werewolf_version}:{self.other_version}"
        )
        return Team.WEREWOLVES if score < threshold else Team.VILLAGERS

    def _log_werewolf_win_script(self):
        self.logger.log_night_action(
            self.game_id,
            {"actor": "player_0", "action": "kill", "target": "player_2"},
        )
        self.logger.log_night_action(
            self.game_id,
            {"actor": "player_2", "action": "check", "target": "player_5", "result": "villager"},
        )
        self.logger.log_night_action(
            self.game_id,
            {"actor": "player_3", "action": "poison", "target": "player_5"},
        )
        self._kill("player_2", "wolf_kill")
        self._kill("player_5", "witch_poison")
        self._speech("player_2", "我是预言家，但昨晚没有查到狼人。")
        self._vote_result(
            {
                "player_0": "player_5",
                "player_1": "player_5",
                "player_2": "player_0",
                "player_3": "player_5",
                "player_4": "player_0",
                "player_5": "player_0",
            }
        )

    def _log_villager_win_script(self):
        self.logger.log_night_action(
            self.game_id,
            {"actor": "player_0", "action": "kill", "target": "player_3"},
        )
        self.logger.log_night_action(
            self.game_id,
            {"actor": "player_2", "action": "check", "target": "player_0", "result": "werewolf"},
        )
        self.logger.log_night_action(
            self.game_id,
            {"actor": "player_3", "action": "save", "target": "player_3"},
        )
        self.logger.log_night_action(
            self.game_id,
            {"actor": "player_3", "action": "poison", "target": "player_1"},
        )
        self._kill("player_1", "witch_poison")
        self._speech("player_2", "我是预言家，昨晚查验 Alice 是狼人，请大家归票。")
        self._vote_result(
            {
                "player_0": "player_5",
                "player_1": "player_5",
                "player_2": "player_0",
                "player_3": "player_0",
                "player_4": "player_0",
                "player_5": "player_0",
            }
        )
        self._kill("player_0", "vote")

    def _kill(self, player_id: str, cause: str):
        self.state.players[player_id].is_alive = False
        self.logger.log_death(self.game_id, player_id, cause)

    def _speech(self, player_id: str, content: str):
        self.logger._append_log(
            self.game_id,
            {
                "timestamp": datetime.now().isoformat(),
                "type": "speech",
                "round_number": 1,
                "player_id": player_id,
                "content": content,
            },
        )

    def _vote_result(self, votes: dict):
        player_names = {
            player_id: player.name
            for player_id, player in self.state.players.items()
        }
        vote_text = " | ".join(
            f"{player_names[voter_id]}: {player_names[target_id]}"
            for voter_id, target_id in votes.items()
        )
        self.logger._append_log(
            self.game_id,
            {
                "timestamp": datetime.now().isoformat(),
                "type": "vote_result",
                "round_number": 1,
                "content": f"投票结果: {vote_text}",
            },
        )

    def _stable_score(self, text: str) -> float:
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return int(digest[:12], 16) / float(0xFFFFFFFFFFFF)

    def _version_strength(self, version: str) -> int:
        if not version or not version.startswith("v"):
            return 0
        try:
            return int(version.rsplit(".", 1)[1])
        except (IndexError, ValueError):
            return 0
