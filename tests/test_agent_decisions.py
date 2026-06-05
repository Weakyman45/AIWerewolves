import asyncio

from backend.agents.base import AgentAction, BaseAgent
from backend.core.models import AgentDecision, Role


class DummyAgent(BaseAgent):
    def get_system_prompt(self):
        return "dummy"

    async def make_night_action(self, game_state):
        return AgentDecision(decision_type="no_action", reasoning="", raw_output="")

    async def make_speech(self, game_state):
        return AgentDecision(decision_type="speech", reasoning="", raw_output="")

    async def make_vote(self, game_state):
        return AgentDecision(decision_type="vote", reasoning="", raw_output="")


def _agent_with_action(action: AgentAction) -> DummyAgent:
    agent = DummyAgent("player_0", "Alice", Role.VILLAGER)

    async def fake_action(_game_state, _action_type, _extra_instructions=""):
        return action

    agent._call_llm_for_action = fake_action
    return agent


def test_sheriff_election_does_not_treat_negative_text_as_run():
    agent = _agent_with_action(
        AgentAction(
            reasoning="隐藏身份，选择不上警",
            speech="我不上警，警下会认真投票",
        )
    )

    decision = asyncio.run(agent.make_sheriff_election({}))

    assert decision.decision_type == "stay"


def test_sheriff_election_uses_explicit_decision_type():
    agent = _agent_with_action(
        AgentAction(
            decision_type="run",
            reasoning="争夺警徽",
            speech="我上警竞选警长",
        )
    )

    decision = asyncio.run(agent.make_sheriff_election({}))

    assert decision.decision_type == "run"


def test_sheriff_retreat_does_not_treat_negative_text_as_retreat():
    agent = _agent_with_action(
        AgentAction(
            reasoning="继续留在警上",
            speech="我不退水，继续竞争警徽",
        )
    )

    decision = asyncio.run(agent.make_retreat({}))

    assert decision.decision_type == "stay"
