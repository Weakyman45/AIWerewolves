import uuid
import random
import asyncio
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from backend.core.models import (
    GameState,
    PlayerState,
    Role,
    GamePhase,
    Team,
    RoundRecord,
    NightAction,
    NightActionRecord,
    VoteRecord,
    GameMessage,
    AgentDecision,
)
from backend.agents.base import BaseAgent
from backend.agents.factory import AgentFactory
from backend.agents.roles.witch import WitchAgent
from backend.agents.roles.seer import SeerAgent
from backend.agents.roles.hunter import HunterAgent
from backend.core.logger import GameLogger


class WerewolfGame:
    def __init__(self, player_names: List[str], logger: Optional[GameLogger] = None):
        self.game_id = str(uuid.uuid4())
        self.logger = logger or GameLogger()
        self.player_names = player_names
        self.players: Dict[str, BaseAgent] = {}
        self.player_states: Dict[str, PlayerState] = {}
        self.state = GameState(game_id=self.game_id)
        self.death_queue: List[Tuple[str, str]] = []
        
        # 暂停控制
        self._is_paused = False
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # 初始状态为未暂停
        
        self._setup_players()
        self._init_game_state()
    
    def pause(self):
        """暂停游戏"""
        self._is_paused = True
        self._pause_event.clear()
    
    def resume(self):
        """继续游戏"""
        self._is_paused = False
        self._pause_event.set()
    
    @property
    def is_paused(self) -> bool:
        return self._is_paused
    
    async def _wait_if_paused(self):
        """如果暂停则等待"""
        if self._is_paused:
            await self._pause_event.wait()
    
    def _setup_players(self):
        roles = self._assign_roles(len(self.player_names))
        for i, (name, role) in enumerate(zip(self.player_names, roles)):
            player_id = f"player_{i}"
            agent = AgentFactory.create_agent(role, player_id, name)
            self.players[player_id] = agent
            self.player_states[player_id] = PlayerState(
                player_id=player_id,
                name=name,
                role=role,
                is_alive=True
            )
    
    def _assign_roles(self, num_players: int) -> List[Role]:
        if num_players == 9:
            roles = [
                Role.WEREWOLF, Role.WEREWOLF, Role.WEREWOLF,
                Role.SEER, Role.WITCH, Role.HUNTER,
                Role.VILLAGER, Role.VILLAGER, Role.VILLAGER
            ]
        elif num_players == 8:
            roles = [
                Role.WEREWOLF, Role.WEREWOLF, Role.WEREWOLF,
                Role.SEER, Role.WITCH, Role.HUNTER,
                Role.VILLAGER, Role.VILLAGER
            ]
        elif num_players == 7:
            roles = [
                Role.WEREWOLF, Role.WEREWOLF,
                Role.SEER, Role.WITCH, Role.HUNTER,
                Role.VILLAGER, Role.VILLAGER
            ]
        elif num_players == 6:
            roles = [
                Role.WEREWOLF, Role.WEREWOLF,
                Role.SEER, Role.WITCH, Role.HUNTER,
                Role.VILLAGER
            ]
        else:
            roles = [
                Role.WEREWOLF, Role.WEREWOLF, Role.WEREWOLF,
                Role.SEER, Role.WITCH, Role.HUNTER,
                Role.VILLAGER, Role.VILLAGER, Role.VILLAGER
            ]
        
        random.shuffle(roles)
        return roles
    
    def _init_game_state(self):
        self.state.players = self.player_states.copy()
        self.state.current_phase = GamePhase.NIGHT
        self.state.current_round = 1
        self.state.history = []
        self.logger.log_game_start(self.state)
    
    def _get_agent_visible_state(self, player_id: str) -> dict:
        viewer = self.player_states.get(player_id)
        if not viewer:
            return {}
        
        filtered_players = {}
        for pid, p in self.player_states.items():
            filtered_player = {
                "player_id": p.player_id,
                "name": p.name,
                "is_alive": p.is_alive,
                "is_sheriff": p.is_sheriff,
                "in_sheriff_election": p.in_sheriff_election,
            }
            
            if pid == player_id:
                filtered_player["role"] = p.role.value
            elif viewer.role == Role.WEREWOLF and p.role == Role.WEREWOLF:
                filtered_player["role"] = p.role.value
            
            filtered_players[pid] = filtered_player
        
        return {
            "game_id": self.state.game_id,
            "players": filtered_players,
            "current_phase": self.state.current_phase.value,
            "current_round": self.state.current_round,
            "winner": self.state.winner.value if self.state.winner else None,
            "sheriff_id": self.state.sheriff_id,
            "sheriff_lost": self.state.sheriff_lost,
            "pk_rounds": self.state.pk_rounds,
        }
    
    async def run(self) -> Team:
        while self.state.winner is None:
            await self._wait_if_paused()
            await self._run_round()
        
        self.state.ended_at = datetime.now()
        self.logger.log_game_end(self.state)
        return self.state.winner
    
    async def _run_round(self):
        await self._wait_if_paused()
        
        round_record = RoundRecord(
            round_number=self.state.current_round,
            phase=GamePhase.NIGHT
        )
        self.state.history.append(round_record)
        
        await self._run_night_phase(round_record)
        
        if self.state.winner is not None:
            return
        
        await self._process_deaths(round_record)
        
        if self.state.winner is not None:
            return
        
        if self.state.current_round == 1 and not self.state.sheriff_id and not self.state.sheriff_lost:
            await self._run_sheriff_election(round_record)
        
        if self.state.winner is not None:
            return
        
        await self._run_day_phase(round_record)
        
        if self.state.winner is not None:
            return
        
        await self._process_deaths(round_record)
        
        self.state.current_round += 1
    
    async def _run_sheriff_election(self, round_record: RoundRecord):
        await self._wait_if_paused()
        
        self.state.current_phase = GamePhase.SHERIFF_ELECTION
        self.logger.log_phase_change(self.game_id, self.state.current_round, "警长竞选")
        await asyncio.sleep(1)
        
        sheriff_candidates = []
        stay_in_election = []
        alive_player_ids = [pid for pid, p in self.player_states.items() if p.is_alive]
        
        # 并发收集所有上警决定，提升速度
        async def get_sheriff_election_decision(player_id):
            await self._wait_if_paused()
            agent = self.players[player_id]
            visible_state = self._get_agent_visible_state(player_id)
            decision = await agent.make_sheriff_election(visible_state)
            return player_id, decision
        
        # 并发调用所有玩家的上警决策
        tasks = [get_sheriff_election_decision(pid) for pid in alive_player_ids]
        results = await asyncio.gather(*tasks)
        
        sheriff_candidates = []
        stay_in_election = []
        for player_id, decision in results:
            self.logger.log_agent_decision(self.game_id, player_id, decision)
            if decision.decision_type == "run":
                sheriff_candidates.append(player_id)
                self.player_states[player_id].in_sheriff_election = True
            else:
                stay_in_election.append(player_id)
        
        # 确保预言家必须上警
        seer_id = None
        for pid in alive_player_ids:
            if self.player_states[pid].role == Role.SEER:
                seer_id = pid
                break
        
        if seer_id and seer_id not in sheriff_candidates:
            sheriff_candidates.append(seer_id)
            self.player_states[seer_id].in_sheriff_election = True
            if seer_id in stay_in_election:
                stay_in_election.remove(seer_id)
        
        # 确保至少有一个狼人上警
        wolf_ids = [pid for pid in alive_player_ids if self.player_states[pid].role == Role.WEREWOLF]
        wolf_on_board = [pid for pid in wolf_ids if pid in sheriff_candidates]
        
        if not wolf_on_board and wolf_ids:
            # 随机选择一个狼人上警
            random_wolf = random.choice(wolf_ids)
            sheriff_candidates.append(random_wolf)
            self.player_states[random_wolf].in_sheriff_election = True
            if random_wolf in stay_in_election:
                stay_in_election.remove(random_wolf)
        
        # 汇总显示结果
        candidate_names = [self.player_states[pid].name for pid in sheriff_candidates]
        stay_names = [self.player_states[pid].name for pid in stay_in_election]
        
        import json
        log_path = f"logs/game_{self.game_id}.jsonl"
        with open(log_path, "a", encoding="utf-8") as f:
            if candidate_names and stay_names:
                log_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "type": "sheriff_candidates",
                    "content": f"上警玩家: {', '.join(candidate_names)} | 警下玩家: {', '.join(stay_names)}"
                }
            elif candidate_names:
                log_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "type": "sheriff_candidates",
                    "content": f"上警玩家: {', '.join(candidate_names)} | 全员上警"
                }
            else:
                log_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "type": "sheriff_candidates",
                    "content": "上警玩家: 无人上警"
                }
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        
        if not sheriff_candidates:
            self.state.sheriff_lost = True
            # 清理所有玩家的上警状态
            for pid in alive_player_ids:
                self.player_states[pid].in_sheriff_election = False
            import json
            log_path = f"logs/game_{self.game_id}.jsonl"
            with open(log_path, "a", encoding="utf-8") as f:
                log_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "type": "sheriff_lost",
                    "content": "无人上警，警徽流失"
                }
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
            return
        
        if len(sheriff_candidates) == len(alive_player_ids):
            self.state.sheriff_lost = True
            # 清理所有玩家的上警状态
            for pid in alive_player_ids:
                self.player_states[pid].in_sheriff_election = False
            import json
            log_path = f"logs/game_{self.game_id}.jsonl"
            with open(log_path, "a", encoding="utf-8") as f:
                log_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "type": "sheriff_lost",
                    "content": "全员上警，警徽流失"
                }
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
            return
        
        await self._run_sheriff_speeches(sheriff_candidates, round_record)
        
        if self.state.winner is not None:
            return
        
        await self._run_retreat(sheriff_candidates, round_record)
        
        if self.state.winner is not None:
            return
        
        final_candidates = [pid for pid in sheriff_candidates if self.player_states[pid].in_sheriff_election]
        
        if not final_candidates:
            self.state.sheriff_lost = True
            # 清理所有玩家的上警状态
            for pid in alive_player_ids:
                self.player_states[pid].in_sheriff_election = False
            import json
            log_path = f"logs/game_{self.game_id}.jsonl"
            with open(log_path, "a", encoding="utf-8") as f:
                log_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "type": "sheriff_lost",
                    "content": "全部退水，警徽流失"
                }
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
            return
        
        # 警上只有1人时自动当选警长
        if len(final_candidates) == 1:
            sheriff_id = final_candidates[0]
            self.state.sheriff_id = sheriff_id
            self.player_states[sheriff_id].is_sheriff = True
            for pid in sheriff_candidates:
                self.player_states[pid].in_sheriff_election = False
            
            import json
            log_path = f"logs/game_{self.game_id}.jsonl"
            with open(log_path, "a", encoding="utf-8") as f:
                log_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "type": "sheriff_elected",
                    "sheriff_id": sheriff_id,
                    "sheriff_name": self.player_states[sheriff_id].name,
                    "content": f"{self.player_states[sheriff_id].name} 自动当选警长（警上仅1人）"
                }
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        else:
            await self._run_sheriff_vote(final_candidates, round_record)
        
        # 确保所有玩家的上警状态都清理完毕
        for pid in alive_player_ids:
            self.player_states[pid].in_sheriff_election = False
    
    async def _run_sheriff_speeches(self, candidates: List[str], round_record: RoundRecord):
        await self._wait_if_paused()
        
        self.state.current_phase = GamePhase.SHERIFF_SPEECH
        self.logger.log_phase_change(self.game_id, self.state.current_round, "警上发言")
        await asyncio.sleep(1)
        
        random.shuffle(candidates)
        
        for player_id in candidates:
            await self._wait_if_paused()
            
            if not self.player_states[player_id].is_alive:
                continue
            
            agent = self.players[player_id]
            visible_state = self._get_agent_visible_state(player_id)
            decision = await agent.make_sheriff_speech(visible_state)
            self.logger.log_agent_decision(self.game_id, player_id, decision)
            
            import json
            log_path = f"logs/game_{self.game_id}.jsonl"
            with open(log_path, "a", encoding="utf-8") as f:
                log_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "type": "sheriff_speech",
                    "player_id": player_id,
                    "player_name": self.player_states[player_id].name,
                    "content": decision.raw_output
                }
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
            
            msg = GameMessage(
                message_id=str(uuid.uuid4()),
                sender_id=player_id,
                content=decision.raw_output,
                message_type="public"
            )
            round_record.messages.append(msg)
            
            for a in self.players.values():
                a.add_conversation("user", f"{self.player_states[player_id].name}: {msg.content}")
            
            await asyncio.sleep(0.5)
    
    async def _run_retreat(self, candidates: List[str], round_record: RoundRecord):
        await self._wait_if_paused()
        
        self.state.current_phase = GamePhase.SHERIFF_RETREAT
        self.logger.log_phase_change(self.game_id, self.state.current_round, "退水阶段")
        await asyncio.sleep(1)
        
        # 先记录退水的玩家
        retreating_players = []
        
        for player_id in candidates:
            await self._wait_if_paused()
            
            if not self.player_states[player_id].is_alive:
                continue
            
            # 预言家不能退水
            if self.player_states[player_id].role == Role.SEER:
                continue
            
            agent = self.players[player_id]
            visible_state = self._get_agent_visible_state(player_id)
            decision = await agent.make_retreat(visible_state)
            self.logger.log_agent_decision(self.game_id, player_id, decision)
            
            if decision.decision_type == "retreat":
                retreating_players.append(player_id)
        
        # 汇总展示退水结果
        if retreating_players:
            retreat_names = [self.player_states[pid].name for pid in retreating_players]
            import json
            log_path = f"logs/game_{self.game_id}.jsonl"
            with open(log_path, "a", encoding="utf-8") as f:
                log_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "type": "sheriff_retreat",
                    "content": f"退水玩家: {', '.join(retreat_names)}"
                }
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        
        # 执行退水操作
        for player_id in retreating_players:
            self.player_states[player_id].in_sheriff_election = False
    
    async def _run_sheriff_vote(self, candidates: List[str], round_record: RoundRecord, pk_round: int = 0):
        await self._wait_if_paused()
        
        self.state.current_phase = GamePhase.SHERIFF_VOTE
        self.state.pk_rounds = pk_round
        self.logger.log_phase_change(self.game_id, self.state.current_round, f"警长投票 (第{pk_round+1}轮)")
        await asyncio.sleep(1)
        
        alive_player_ids = [pid for pid, p in self.player_states.items() if p.is_alive]
        voters = [pid for pid in alive_player_ids if not self.player_states[pid].in_sheriff_election]
        
        if not voters:
            self.state.sheriff_lost = True
            # 清理所有玩家的上警状态
            for pid in alive_player_ids:
                self.player_states[pid].in_sheriff_election = False
            import json
            log_path = f"logs/game_{self.game_id}.jsonl"
            with open(log_path, "a", encoding="utf-8") as f:
                log_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "type": "sheriff_lost",
                    "content": "无警下玩家，警徽流失"
                }
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
            return
        
        votes: Dict[str, List[str]] = {c: [] for c in candidates}
        vote_records = []
        
        # 并发收集所有投票决定，提升速度
        async def get_sheriff_vote_decision(voter_id):
            await self._wait_if_paused()
            agent = self.players[voter_id]
            visible_state = self._get_agent_visible_state(voter_id)
            decision = await agent.make_sheriff_vote(visible_state)
            return voter_id, decision
        
        # 并发调用所有警下玩家的投票决策
        tasks = [get_sheriff_vote_decision(pid) for pid in voters]
        results = await asyncio.gather(*tasks)
        
        for voter_id, decision in results:
            self.logger.log_agent_decision(self.game_id, voter_id, decision)
            
            target_id = decision.target_id
            if target_id and target_id in candidates:
                votes[target_id].append(voter_id)
            
            record = VoteRecord(voter_id=voter_id, target_id=target_id, is_sheriff_vote=True)
            round_record.votes.append(record)
            
            target_name = self.player_states[target_id].name if target_id else "弃票"
            vote_records.append(f"{self.player_states[voter_id].name}: {target_name}")
        
        # 汇总展示投票结果
        import json
        log_path = f"logs/game_{self.game_id}.jsonl"
        with open(log_path, "a", encoding="utf-8") as f:
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "type": "sheriff_vote_result",
                "content": "投票结果: " + " | ".join(vote_records)
            }
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        
        vote_counts = {c: len(v) for c, v in votes.items()}
        
        vote_display = []
        for candidate_id, voter_ids in votes.items():
            voter_names = [self.player_states[vid].name for vid in voter_ids]
            vote_display.append(f"{self.player_states[candidate_id].name}: {len(voter_names)}票 ({', '.join(voter_names)})")
        
        import json
        log_path = f"logs/game_{self.game_id}.jsonl"
        with open(log_path, "a", encoding="utf-8") as f:
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "type": "vote_count",
                "content": " | ".join(vote_display)
            }
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        
        # 将警上投票票型同步到所有玩家知识库
        vote_info = f"警长投票结果：{' | '.join(vote_display)}"
        alive_player_ids = [pid for pid, p in self.player_states.items() if p.is_alive]
        for pid in alive_player_ids:
            self.players[pid].private_knowledge.append(vote_info)
        
        max_votes = max(vote_counts.values())
        top_candidates = [c for c, cnt in vote_counts.items() if cnt == max_votes]
        
        if len(top_candidates) == 1:
            sheriff_id = top_candidates[0]
            self.state.sheriff_id = sheriff_id
            self.player_states[sheriff_id].is_sheriff = True
            for pid in candidates:
                self.player_states[pid].in_sheriff_election = False
            
            import json
            log_path = f"logs/game_{self.game_id}.jsonl"
            with open(log_path, "a", encoding="utf-8") as f:
                log_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "type": "sheriff_elected",
                    "sheriff_id": sheriff_id,
                    "sheriff_name": self.player_states[sheriff_id].name,
                    "content": f"{self.player_states[sheriff_id].name} 当选警长"
                }
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        else:
            if pk_round >= 2:
                self.state.sheriff_lost = True
                # 清理所有玩家的上警状态
                for pid in alive_player_ids:
                    self.player_states[pid].in_sheriff_election = False
                import json
                log_path = f"logs/game_{self.game_id}.jsonl"
                with open(log_path, "a", encoding="utf-8") as f:
                    log_entry = {
                        "timestamp": datetime.now().isoformat(),
                        "type": "sheriff_lost",
                        "content": "连续三轮平票，警徽流失"
                    }
                    f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
                return
            
            await self._run_pk_phase(top_candidates, round_record)
            await self._run_sheriff_vote(top_candidates, round_record, pk_round + 1)
    
    async def _run_pk_phase(self, candidates: List[str], round_record: RoundRecord):
        await self._wait_if_paused()
        
        self.state.current_phase = GamePhase.SHERIFF_PK
        self.logger.log_phase_change(self.game_id, self.state.current_round, "PK发言")
        await asyncio.sleep(1)
        
        for player_id in candidates:
            await self._wait_if_paused()
            
            if not self.player_states[player_id].is_alive:
                continue
            
            agent = self.players[player_id]
            visible_state = self._get_agent_visible_state(player_id)
            decision = await agent.make_pk_speech(visible_state)
            self.logger.log_agent_decision(self.game_id, player_id, decision)
            
            import json
            log_path = f"logs/game_{self.game_id}.jsonl"
            with open(log_path, "a", encoding="utf-8") as f:
                log_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "type": "pk_speech",
                    "player_id": player_id,
                    "player_name": self.player_states[player_id].name,
                    "content": decision.raw_output
                }
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
            
            msg = GameMessage(
                message_id=str(uuid.uuid4()),
                sender_id=player_id,
                content=decision.raw_output,
                message_type="public"
            )
            round_record.messages.append(msg)
            
            for a in self.players.values():
                a.add_conversation("user", f"{self.player_states[player_id].name}: {msg.content}")
            
            await asyncio.sleep(0.5)
    
    async def _run_night_phase(self, round_record: RoundRecord):
        await self._wait_if_paused()
        
        self.state.current_phase = GamePhase.NIGHT
        self.logger.log_phase_change(self.game_id, self.state.current_round, "夜晚")
        await asyncio.sleep(1)
        
        kill_victim = await self._process_wolf_kill(round_record)
        await asyncio.sleep(1)
        
        await self._process_seer_check(round_record)
        await asyncio.sleep(1)
        
        await self._process_witch_action(round_record, kill_victim)
        await asyncio.sleep(1)
        
        if kill_victim and not self._was_saved(kill_victim, round_record):
            self.death_queue.append((kill_victim, "wolf_kill"))
    
    async def _process_wolf_kill(self, round_record: RoundRecord) -> Optional[str]:
        await self._wait_if_paused()
        
        wolves = [p for p in self.players.values() if p.role == Role.WEREWOLF and self.player_states[p.player_id].is_alive]
        if not wolves:
            return None
        
        wolf = wolves[0]
        visible_state = self._get_agent_visible_state(wolf.player_id)
        decision = await wolf.make_night_action(visible_state)
        self.logger.log_agent_decision(self.game_id, wolf.player_id, decision)
        
        target_id = decision.target_id
        
        if target_id:
            alive_ids = [pid for pid, p in self.player_states.items() if p.is_alive and p.role != Role.WEREWOLF]
            if not alive_ids:
                return None
            if target_id not in alive_ids:
                target_id = random.choice(alive_ids)
        
        if target_id:
            record = NightActionRecord(
                actor_id=wolf.player_id,
                action=NightAction.KILL,
                target_id=target_id,
                success=True
            )
            round_record.night_actions.append(record)
            self.logger.log_night_action(self.game_id, {
                "actor": wolf.player_id,
                "action": "kill",
                "target": target_id
            })
        
        return target_id
    
    async def _process_seer_check(self, round_record: RoundRecord):
        await self._wait_if_paused()
        
        seers = [p for p in self.players.values() if p.role == Role.SEER and self.player_states[p.player_id].is_alive]
        if not seers:
            return
        
        seer = seers[0]
        visible_state = self._get_agent_visible_state(seer.player_id)
        decision = await seer.make_night_action(visible_state)
        self.logger.log_agent_decision(self.game_id, seer.player_id, decision)
        
        target_id = decision.target_id
        if target_id and target_id in self.player_states:
            is_werewolf = self.player_states[target_id].role == Role.WEREWOLF
            
            if isinstance(seer, SeerAgent):
                seer.add_check_result(target_id, is_werewolf)
                seer.add_private_knowledge(f"查验结果: {self.player_states[target_id].name} 是{'狼人' if is_werewolf else '好人'}")
            
            record = NightActionRecord(
                actor_id=seer.player_id,
                action=NightAction.CHECK,
                target_id=target_id,
                success=True
            )
            round_record.night_actions.append(record)
            self.logger.log_night_action(self.game_id, {
                "actor": seer.player_id,
                "action": "check",
                "target": target_id,
                "result": "werewolf" if is_werewolf else "villager"
            })
    
    async def _process_witch_action(self, round_record: RoundRecord, kill_victim: Optional[str]):
        await self._wait_if_paused()
        
        witches = [p for p in self.players.values() if p.role == Role.WITCH and self.player_states[p.player_id].is_alive]
        if not witches:
            return
        
        witch = witches[0]
        if isinstance(witch, WitchAgent):
            witch.set_night_kill(kill_victim)
            witch.add_private_knowledge(f"解药已使用: {witch.has_used_save}")
            witch.add_private_knowledge(f"毒药已使用: {witch.has_used_poison}")
        
        visible_state = self._get_agent_visible_state(witch.player_id)
        decision = await witch.make_night_action(visible_state)
        self.logger.log_agent_decision(self.game_id, witch.player_id, decision)
        
        action_type = decision.decision_type
        target_id = decision.target_id
        
        if action_type == "save" and target_id and isinstance(witch, WitchAgent):
            if not witch.has_used_save:
                witch.use_save()
                witch.add_private_knowledge(f"使用解药救了 {self.player_states[target_id].name}")
                record = NightActionRecord(
                    actor_id=witch.player_id,
                    action=NightAction.SAVE,
                    target_id=target_id,
                    success=True
                )
                round_record.night_actions.append(record)
                self.logger.log_night_action(self.game_id, {
                    "actor": witch.player_id,
                    "action": "save",
                    "target": target_id
                })
        
        elif action_type == "poison" and target_id and isinstance(witch, WitchAgent):
            if not witch.has_used_poison:
                witch.use_poison()
                witch.add_private_knowledge(f"使用毒药毒了 {self.player_states[target_id].name}")
                record = NightActionRecord(
                    actor_id=witch.player_id,
                    action=NightAction.POISON,
                    target_id=target_id,
                    success=True
                )
                round_record.night_actions.append(record)
                self.logger.log_night_action(self.game_id, {
                    "actor": witch.player_id,
                    "action": "poison",
                    "target": target_id
                })
                self.death_queue.append((target_id, "witch_poison"))
    
    def _was_saved(self, victim_id: str, round_record: RoundRecord) -> bool:
        for action in round_record.night_actions:
            if action.action == NightAction.SAVE and action.target_id == victim_id:
                return True
        return False
    
    async def _process_deaths(self, round_record: RoundRecord):
        await self._wait_if_paused()
        
        while self.death_queue:
            await self._wait_if_paused()
            
            player_id, cause = self.death_queue.pop(0)
            
            if not self.player_states[player_id].is_alive:
                continue
            
            self.player_states[player_id].is_alive = False
            round_record.deaths.append(player_id)
            self.logger.log_death(self.game_id, player_id, cause)
            
            # 将死亡信息同步到所有玩家对话历史
            death_msg = f"{self.player_states[player_id].name} 死亡"
            for a in self.players.values():
                a.add_conversation("system", death_msg)
            
            await self._process_hunter_shot(player_id, cause, round_record)
            
            winner = self._check_winner()
            if winner:
                self.state.winner = winner
                return
            
            # 处理警长死亡的警徽移交
            if self.player_states[player_id].is_sheriff:
                self.player_states[player_id].is_sheriff = False
                sheriff_agent = self.players[player_id]
                visible_state = self._get_agent_visible_state(player_id)
                decision = await sheriff_agent.make_sheriff_death_decision(visible_state)
                self.logger.log_agent_decision(self.game_id, player_id, decision)
                
                import json
                log_path = f"logs/game_{self.game_id}.jsonl"
                with open(log_path, "a", encoding="utf-8") as f:
                    if decision.decision_type == "pass" and decision.target_id:
                        new_sheriff_id = decision.target_id
                        self.state.sheriff_id = new_sheriff_id
                        self.player_states[new_sheriff_id].is_sheriff = True
                        log_entry = {
                            "timestamp": datetime.now().isoformat(),
                            "type": "sheriff_passed",
                            "old_sheriff_name": self.player_states[player_id].name,
                            "new_sheriff_id": new_sheriff_id,
                            "new_sheriff_name": self.player_states[new_sheriff_id].name,
                            "content": f"{self.player_states[player_id].name} 将警徽移交给 {self.player_states[new_sheriff_id].name}"
                        }
                        # 同步警徽移交信息到所有玩家
                        pass_msg = f"{self.player_states[player_id].name} 将警徽移交给 {self.player_states[new_sheriff_id].name}，{self.player_states[new_sheriff_id].name} 成为新警长"
                        for a in self.players.values():
                            a.add_conversation("system", pass_msg)
                    else:
                        self.state.sheriff_id = None
                        log_entry = {
                            "timestamp": datetime.now().isoformat(),
                            "type": "sheriff_destroyed",
                            "sheriff_name": self.player_states[player_id].name,
                            "content": f"{self.player_states[player_id].name} 撕掉警徽，本局不再有警长"
                        }
                        # 同步警徽撕掉信息到所有玩家
                        destroy_msg = f"{self.player_states[player_id].name} 撕掉警徽，本局不再有警长"
                        for a in self.players.values():
                            a.add_conversation("system", destroy_msg)
                    f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    
    async def _process_hunter_shot(self, dead_player_id: str, cause: str, round_record: RoundRecord):
        await self._wait_if_paused()
        
        if self.player_states[dead_player_id].role != Role.HUNTER:
            return
        
        if cause == "witch_poison":
            return
        
        hunter = self.players[dead_player_id]
        if not isinstance(hunter, HunterAgent):
            return
        
        if hunter.has_shot:
            return
        
        visible_state = self._get_agent_visible_state(dead_player_id)
        decision = await hunter.make_shot(visible_state)
        self.logger.log_agent_decision(self.game_id, dead_player_id, decision)
        
        target_id = decision.target_id
        if target_id and self.player_states[target_id].is_alive:
            alive_ids = [pid for pid, p in self.player_states.items() if p.is_alive]
            if target_id not in alive_ids:
                target_id = random.choice(alive_ids) if alive_ids else None
            
            if target_id:
                self.death_queue.append((target_id, "hunter_shot"))
    
    async def _run_day_phase(self, round_record: RoundRecord):
        await self._wait_if_paused()
        
        self.state.current_phase = GamePhase.DAY
        self.logger.log_phase_change(self.game_id, self.state.current_round, "白天")
        await asyncio.sleep(1)
        
        speak_order = await self._determine_speak_order()
        self.state.speak_order = speak_order
        
        await self._run_speeches(round_record, speak_order)
        await asyncio.sleep(1)
        
        if self.state.winner is not None:
            return
        
        voted_out = await self._run_full_voting_cycle(round_record)
        
        if voted_out:
            await self._run_last_words(voted_out, round_record)
            self.death_queue.append((voted_out, "voted_out"))
    
    async def _determine_speak_order(self) -> List[str]:
        alive_player_ids = [pid for pid, p in self.player_states.items() if p.is_alive]
        
        if self.state.sheriff_id and self.state.sheriff_id in alive_player_ids:
            sheriff_agent = self.players[self.state.sheriff_id]
            visible_state = self._get_agent_visible_state(self.state.sheriff_id)
            decision = await sheriff_agent.make_speak_direction(visible_state)
            self.logger.log_agent_decision(self.game_id, self.state.sheriff_id, decision)
            
            direction = decision.decision_type
            
            sheriff_idx = alive_player_ids.index(self.state.sheriff_id)
            
            if direction == "right":
                speak_order = alive_player_ids[sheriff_idx+1:] + alive_player_ids[:sheriff_idx]
            else:
                speak_order = alive_player_ids[:sheriff_idx][::-1] + alive_player_ids[sheriff_idx+1:][::-1]
            
            import json
            log_path = f"logs/game_{self.game_id}.jsonl"
            with open(log_path, "a", encoding="utf-8") as f:
                log_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "type": "speak_direction",
                    "sheriff_id": self.state.sheriff_id,
                    "direction": direction,
                    "content": f"警长决定从{'右边' if direction == 'right' else '左边'}开始发言"
                }
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        else:
            random.shuffle(alive_player_ids)
            speak_order = alive_player_ids
        
        return speak_order
    
    async def _run_speeches(self, round_record: RoundRecord, speak_order: List[str]):
        await self._wait_if_paused()
        
        for player_id in speak_order:
            await self._wait_if_paused()
            
            if not self.player_states[player_id].is_alive:
                continue
            
            agent = self.players[player_id]
            visible_state = self._get_agent_visible_state(player_id)
            decision = await agent.make_speech(visible_state)
            self.logger.log_agent_decision(self.game_id, player_id, decision)
            
            # 处理狼人自爆
            if decision.decision_type == "bomb" and self.player_states[player_id].role == Role.WEREWOLF:
                # 处理自爆
                self.player_states[player_id].is_alive = False
                round_record.deaths.append(player_id)
                self.logger.log_death(self.game_id, player_id, "wolf_bomb")
                
                import json
                log_path = f"logs/game_{self.game_id}.jsonl"
                with open(log_path, "a", encoding="utf-8") as f:
                    log_entry = {
                        "timestamp": datetime.now().isoformat(),
                        "type": "wolf_bomb",
                        "player_id": player_id,
                        "player_name": self.player_states[player_id].name,
                        "content": f"{self.player_states[player_id].name} 自爆，白天立即结束进入黑夜"
                    }
                    f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
                
                # 同步自爆信息到所有玩家
                bomb_msg = f"{self.player_states[player_id].name} 自爆，白天立即结束进入黑夜"
                for a in self.players.values():
                    a.add_conversation("system", bomb_msg)
                
                # 直接返回，终止发言流程
                return
            
            # 正常发言逻辑
            import json
            log_path = f"logs/game_{self.game_id}.jsonl"
            with open(log_path, "a", encoding="utf-8") as f:
                log_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "type": "speech",
                    "player_id": player_id,
                    "player_name": self.player_states[player_id].name,
                    "content": decision.raw_output
                }
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
            
            msg = GameMessage(
                message_id=str(uuid.uuid4()),
                sender_id=player_id,
                content=decision.raw_output,
                message_type="public"
            )
            round_record.messages.append(msg)
            
            for a in self.players.values():
                a.add_conversation("user", f"{self.player_states[player_id].name}: {msg.content}")
            
            await asyncio.sleep(0.5)
    
    async def _run_full_voting_cycle(self, round_record: RoundRecord) -> Optional[str]:
        pk_rounds = 0
        max_pk_rounds = 3
        
        while pk_rounds < max_pk_rounds:
            await self._wait_if_paused()
            
            if pk_rounds == 0:
                self.state.current_phase = GamePhase.VOTING
                self.logger.log_phase_change(self.game_id, self.state.current_round, "放逐投票")
            else:
                self.state.current_phase = GamePhase.VOTING
                self.logger.log_phase_change(self.game_id, self.state.current_round, f"平票PK投票 (第{pk_rounds}轮)")
            
            await asyncio.sleep(1)
            
            result = await self._run_voting_round(round_record, pk_rounds > 0)
            
            if result == "all_abstain":
                import json
                log_path = f"logs/game_{self.game_id}.jsonl"
                with open(log_path, "a", encoding="utf-8") as f:
                    log_entry = {
                        "timestamp": datetime.now().isoformat(),
                        "type": "vote_result",
                        "content": "全员弃票，无人被放逐"
                    }
                    f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
                return None
            
            if isinstance(result, str):
                return result
            
            candidates = result
            if len(candidates) == 1:
                return candidates[0]
            
            pk_rounds += 1
            if pk_rounds < max_pk_rounds:
                await self._run_pk_speeches(candidates, round_record)
        
        import json
        log_path = f"logs/game_{self.game_id}.jsonl"
        with open(log_path, "a", encoding="utf-8") as f:
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "type": "vote_result",
                "content": "连续3次平票，无人被放逐"
            }
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        return None
    
    async def _run_voting_round(self, round_record: RoundRecord, is_pk: bool = False):
        await self._wait_if_paused()
        
        alive_player_ids = [pid for pid, p in self.player_states.items() if p.is_alive]
        votes: Dict[str, float] = {}
        
        all_votes = []
        
        # 并发收集所有投票决定，提升速度
        async def get_vote_decision(player_id):
            await self._wait_if_paused()
            agent = self.players[player_id]
            visible_state = self._get_agent_visible_state(player_id)
            decision = await agent.make_vote(visible_state)
            return player_id, decision
        
        # 并发调用所有玩家的投票决策
        tasks = [get_vote_decision(pid) for pid in alive_player_ids]
        results = await asyncio.gather(*tasks)
        
        for player_id, decision in results:
            self.logger.log_agent_decision(self.game_id, player_id, decision)
            
            target_id = decision.target_id
            record = VoteRecord(voter_id=player_id, target_id=target_id)
            round_record.votes.append(record)
            
            vote_value = 1.5 if self.player_states[player_id].is_sheriff else 1.0
            
            if target_id:
                if target_id not in votes:
                    votes[target_id] = 0
                votes[target_id] += vote_value
            
            voter_name = self.player_states[player_id].name
            target_name = self.player_states[target_id].name if target_id else "弃票"
            sheriff_mark = " [警长]" if self.player_states[player_id].is_sheriff else ""
            all_votes.append(f"{voter_name}{sheriff_mark}: {target_name}")
        
        # 汇总展示投票结果
        import json
        log_path = f"logs/game_{self.game_id}.jsonl"
        with open(log_path, "a", encoding="utf-8") as f:
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "type": "vote_result",
                "content": "投票结果: " + " | ".join(all_votes)
            }
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        
        self.state.vote_results = votes
        
        if not votes:
            return "all_abstain"
        
        vote_counts = []
        for pid, cnt in votes.items():
            vote_counts.append(f"{self.player_states[pid].name}: {cnt}票")
        
        import json
        log_path = f"logs/game_{self.game_id}.jsonl"
        with open(log_path, "a", encoding="utf-8") as f:
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "type": "vote_count",
                "content": " | ".join(vote_counts)
            }
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        
        max_votes = max(votes.values())
        candidates = [pid for pid, cnt in votes.items() if cnt == max_votes]
        
        return candidates
    
    async def _run_pk_speeches(self, candidates: List[str], round_record: RoundRecord):
        await self._wait_if_paused()
        
        self.state.current_phase = GamePhase.DEFENSE
        self.logger.log_phase_change(self.game_id, self.state.current_round, "平票PK发言")
        await asyncio.sleep(1)
        
        for player_id in candidates:
            await self._wait_if_paused()
            
            if not self.player_states[player_id].is_alive:
                continue
            
            agent = self.players[player_id]
            visible_state = self._get_agent_visible_state(player_id)
            decision = await agent.make_speech(visible_state)
            self.logger.log_agent_decision(self.game_id, player_id, decision)
            
            import json
            log_path = f"logs/game_{self.game_id}.jsonl"
            with open(log_path, "a", encoding="utf-8") as f:
                log_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "type": "pk_speech",
                    "player_id": player_id,
                    "player_name": self.player_states[player_id].name,
                    "content": decision.raw_output
                }
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
            
            msg = GameMessage(
                message_id=str(uuid.uuid4()),
                sender_id=player_id,
                content=decision.raw_output,
                message_type="public"
            )
            round_record.messages.append(msg)
            
            for a in self.players.values():
                a.add_conversation("user", f"{self.player_states[player_id].name} (PK发言): {msg.content}")
            
            await asyncio.sleep(0.5)
    
    async def _run_last_words(self, dead_player_id: str, round_record: RoundRecord):
        await self._wait_if_paused()
        
        # 游戏结束后不再触发遗言环节
        if self.state.winner is not None:
            return
        
        self.state.current_phase = GamePhase.DEFENSE
        self.logger.log_phase_change(self.game_id, self.state.current_round, "遗言")
        await asyncio.sleep(1)
        
        agent = self.players[dead_player_id]
        visible_state = self._get_agent_visible_state(dead_player_id)
        decision = await agent.make_last_words(visible_state)
        self.logger.log_agent_decision(self.game_id, dead_player_id, decision)
        
        import json
        log_path = f"logs/game_{self.game_id}.jsonl"
        with open(log_path, "a", encoding="utf-8") as f:
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "type": "last_words",
                "player_id": dead_player_id,
                "player_name": self.player_states[dead_player_id].name,
                "content": decision.raw_output
            }
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        
        msg = GameMessage(
            message_id=str(uuid.uuid4()),
            sender_id=dead_player_id,
            content=decision.raw_output,
            message_type="public"
        )
        round_record.messages.append(msg)
        
        for a in self.players.values():
            a.add_conversation("user", f"{self.player_states[dead_player_id].name} (遗言): {msg.content}")
        
        await asyncio.sleep(0.5)
    
    def _check_winner(self) -> Optional[Team]:
        alive_wolves = [pid for pid, p in self.player_states.items() 
                       if p.is_alive and p.role == Role.WEREWOLF]
        alive_villagers = [pid for pid, p in self.player_states.items() 
                          if p.is_alive and p.role != Role.WEREWOLF]
        
        if not alive_wolves:
            return Team.VILLAGERS
        
        if len(alive_wolves) >= len(alive_villagers):
            return Team.WEREWOLVES
        
        return None
