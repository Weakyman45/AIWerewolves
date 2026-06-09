from enum import Enum
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional, Dict, Any


class Role(str, Enum):
    WEREWOLF = "werewolf"
    SEER = "seer"
    WITCH = "witch"
    HUNTER = "hunter"
    VILLAGER = "villager"


class GamePhase(str, Enum):
    NIGHT = "night"
    SHERIFF_ELECTION = "sheriff_election"  # 上警竞选阶段
    SHERIFF_SPEECH = "sheriff_speech"  # 警上发言阶段
    SHERIFF_RETREAT = "sheriff_retreat"  # 退水阶段
    SHERIFF_VOTE = "sheriff_vote"  # 警下投票阶段
    SHERIFF_PK = "sheriff_pk"  # PK发言阶段
    DAY = "day"  # 白天发言阶段
    VOTING = "voting"  # 放逐投票阶段
    DEFENSE = "defense"
    GAME_OVER = "game_over"


class Team(str, Enum):
    WEREWOLVES = "werewolves"
    VILLAGERS = "villagers"


class NightAction(str, Enum):
    KILL = "kill"
    CHECK = "check"
    SAVE = "save"
    POISON = "poison"


class PlayerState(BaseModel):
    player_id: str
    name: str
    role: Role
    is_alive: bool = True
    has_used_poison: bool = False
    has_used_save: bool = False
    has_shot: bool = False
    # 警徽相关
    is_sheriff: bool = False  # 是否是警长
    in_sheriff_election: bool = False  # 是否在警上（上警了且没退水）
    will_retreat: bool = False  # 是否准备退水
    is_in_pk: bool = False  # 是否在PK阶段


class GameMessage(BaseModel):
    message_id: str
    timestamp: datetime = datetime.now()
    sender_id: Optional[str] = None
    receiver_ids: Optional[List[str]] = None
    content: str
    message_type: str = "public"


class NightActionRecord(BaseModel):
    actor_id: str
    action: NightAction
    target_id: Optional[str] = None
    success: bool = True


class VoteRecord(BaseModel):
    voter_id: str
    target_id: Optional[str] = None
    timestamp: datetime = datetime.now()
    is_sheriff_vote: bool = False  # 是否是警长投票


class RoundRecord(BaseModel):
    round_number: int
    phase: GamePhase
    messages: List[GameMessage] = []
    night_actions: List[NightActionRecord] = []
    votes: List[VoteRecord] = []
    deaths: List[str] = []
    # 警徽相关
    sheriff_candidates: List[str] = []
    sheriff_votes: Dict[str, List[str]] = {}
    pk_rounds: int = 0


class GameState(BaseModel):
    game_id: str
    players: Dict[str, PlayerState] = {}
    current_phase: GamePhase = GamePhase.NIGHT
    current_round: int = 1
    history: List[RoundRecord] = []
    winner: Optional[Team] = None
    started_at: datetime = datetime.now()
    ended_at: Optional[datetime] = None
    # 警徽相关
    sheriff_id: Optional[str] = None  # 警长ID
    sheriff_lost: bool = False  # 警徽是否流失
    current_speaker_index: int = 0  # 当前发言人索引
    speak_order: List[str] = []  # 发言顺序
    pk_rounds: int = 0  # PK轮数
    vote_results: Optional[Dict[str, float]] = None  # 投票结果（警长1.5票）


class AgentDecision(BaseModel):
    decision_type: str
    target_id: Optional[str] = None
    reasoning: str
    raw_output: str
