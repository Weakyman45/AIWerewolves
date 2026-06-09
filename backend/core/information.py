
from typing import List, Optional, Dict
from backend.core.models import (
    GameState,
    PlayerState,
    GameMessage,
    Role,
    NightActionRecord
)


class InformationFilter:
    @staticmethod
    def get_filtered_game_state(game_state, viewer_id: str) -> dict:
        viewer = game_state.players.get(viewer_id)
        if not viewer:
            return {}

        filtered_players = {}
        for pid, player in game_state.players.items():
            filtered_player = {
                "player_id": player.player_id,
                "name": player.name,
                "is_alive": player.is_alive,
            }

            if pid == viewer_id:
                filtered_player["role"] = player.role
            elif viewer.role == Role.WEREWOLF and player.role == Role.WEREWOLF:
                filtered_player["role"] = player.role

            filtered_players[pid] = filtered_player

        return {
            "game_id": game_state.game_id,
            "players": filtered_players,
            "current_phase": game_state.current_phase,
            "current_round": game_state.current_round,
            "winner": game_state.winner,
        }

    @staticmethod
    def get_visible_messages(game_state, viewer_id: str) -> List[GameMessage]:
        visible = []
        for msg in game_state.history:
            for m in msg.messages:
                if m.message_type == "public":
                    visible.append(m)
                elif viewer_id in (m.receiver_ids or []):
                    visible.append(m)
                elif m.sender_id == viewer_id:
                    visible.append(m)
        return visible

    @staticmethod
    def get_visible_night_actions(game_state, viewer_id: str) -> List[NightActionRecord]:
        viewer = game_state.players.get(viewer_id)
        if not viewer:
            return []

        visible = []
        for round_rec in game_state.history:
            for action in round_rec.night_actions:
                if action.actor_id == viewer_id:
                    visible.append(action)
                elif viewer.role == Role.WEREWOLF and action.action.value == "kill":
                    visible.append(action)
                elif viewer.role == Role.SEER and action.actor_id == viewer_id:
                    visible.append(action)
                elif viewer.role == Role.WITCH:
                    if action.action.value in ["save", "poison"]:
                        if action.actor_id == viewer_id:
                            visible.append(action)
        return visible

    @staticmethod
    def get_teammates(game_state, viewer_id: str) -> List[str]:
        viewer = game_state.players.get(viewer_id)
        if not viewer or viewer.role != Role.WEREWOLF:
            return []

        teammates = []
        for pid, player in game_state.players.items():
            if pid != viewer_id and player.role == Role.WEREWOLF:
                teammates.append(pid)
        return teammates

