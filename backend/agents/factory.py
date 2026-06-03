
from backend.core.models import Role
from backend.agents.roles.werewolf import WerewolfAgent
from backend.agents.roles.seer import SeerAgent
from backend.agents.roles.witch import WitchAgent
from backend.agents.roles.hunter import HunterAgent
from backend.agents.roles.villager import VillagerAgent


class AgentFactory:
    @staticmethod
    def create_agent(role, player_id, name, system_prompt=None):
        if role == Role.WEREWOLF:
            agent = WerewolfAgent(player_id, name)
        elif role == Role.SEER:
            agent = SeerAgent(player_id, name)
        elif role == Role.WITCH:
            agent = WitchAgent(player_id, name)
        elif role == Role.HUNTER:
            agent = HunterAgent(player_id, name)
        elif role == Role.VILLAGER:
            agent = VillagerAgent(player_id, name)
        else:
            raise ValueError(f"Unknown role: {role}")
        agent.set_system_prompt_override(system_prompt)
        return agent
