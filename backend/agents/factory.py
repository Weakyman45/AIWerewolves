
from backend.core.models import Role
from backend.agents.roles.werewolf import WerewolfAgent
from backend.agents.roles.seer import SeerAgent
from backend.agents.roles.witch import WitchAgent
from backend.agents.roles.hunter import HunterAgent
from backend.agents.roles.villager import VillagerAgent


class AgentFactory:
    @staticmethod
    def create_agent(role, player_id, name):
        if role == Role.WEREWOLF:
            return WerewolfAgent(player_id, name)
        elif role == Role.SEER:
            return SeerAgent(player_id, name)
        elif role == Role.WITCH:
            return WitchAgent(player_id, name)
        elif role == Role.HUNTER:
            return HunterAgent(player_id, name)
        elif role == Role.VILLAGER:
            return VillagerAgent(player_id, name)
        else:
            raise ValueError(f"Unknown role: {role}")

