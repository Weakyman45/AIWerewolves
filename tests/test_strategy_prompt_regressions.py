from pathlib import Path

import pytest


def test_v013_werewolf_prompt_contains_short_game_survival_constraints():
    repo_root = Path(__file__).resolve().parents[1]
    prompt_path = repo_root / "strategies" / "v0.1.3" / "werewolf.txt"
    if not prompt_path.exists():
        pytest.skip("strategy prompts are optional local artifacts")

    prompt = prompt_path.read_text(encoding="utf-8")

    required_phrases = [
        "D1 狼人不被推出",
        "不要主动踩以下位置",
        "女巫声称者",
        "银水",
        "预言家声称者",
        "不孤票真预/女巫/银水",
        "如果队友已经明显崩盘，优先卖队友",
    ]
    for phrase in required_phrases:
        assert phrase in prompt


def test_v014_werewolf_prompt_blocks_unsupported_d1_pushes():
    repo_root = Path(__file__).resolve().parents[1]
    prompt_path = repo_root / "strategies" / "v0.1.4" / "werewolf.txt"
    if not prompt_path.exists():
        pytest.skip("strategy prompts are optional local artifacts")

    prompt = prompt_path.read_text(encoding="utf-8")

    required_phrases = [
        "D1 前置位没有硬信息时，不点名踩人",
        "没有身份声称、查验、银水/金水、票型或多人共识",
        "唯一预言家起跳且无人对跳时，普通狼不要攻击预言家",
        "如果你前面质疑过的人后来成为金水/银水/预言家/女巫保护位，立刻收回",
        "只在已有公开压力/硬矛盾后",
    ]
    for phrase in required_phrases:
        assert phrase in prompt


def test_v015_werewolf_prompt_blocks_repeated_low_risk_speech():
    repo_root = Path(__file__).resolve().parents[1]
    prompt_path = repo_root / "strategies" / "v0.1.5" / "werewolf.txt"
    if not prompt_path.exists():
        pytest.skip("strategy prompts are optional local artifacts")

    prompt = prompt_path.read_text(encoding="utf-8")

    required_phrases = [
        "低风险表水不能复读前置位或队友的原话",
        "必须换句式",
        "非攻击性观察",
        "照搬发言/无独立逻辑",
    ]
    for phrase in required_phrases:
        assert phrase in prompt


def test_v016_werewolf_prompt_requires_checkkill_defense():
    repo_root = Path(__file__).resolve().parents[1]
    prompt_path = repo_root / "strategies" / "v0.1.6" / "werewolf.txt"
    if not prompt_path.exists():
        pytest.skip("strategy prompts are optional local artifacts")

    prompt = prompt_path.read_text(encoding="utf-8")

    required_phrases = [
        "被查杀时切换到 defense",
        "不能继续普通低风险表水",
        "我不认这个查杀",
        "我和查杀我的预言家二选一",
        "你的投票允许投查杀你的预言家",
    ]
    for phrase in required_phrases:
        assert phrase in prompt


def test_v017_werewolf_prompt_requires_preemptive_fake_seer_and_rescue_vote():
    repo_root = Path(__file__).resolve().parents[1]
    prompt_path = repo_root / "strategies" / "v0.1.7" / "werewolf.txt"
    if not prompt_path.exists():
        pytest.skip("strategy prompts are optional local artifacts")

    prompt = prompt_path.read_text(encoding="utf-8")

    required_phrases = [
        "前置位悍跳触发",
        "狼队需要有人承担 fake_seer",
        "末置位真预单边报查杀",
        "队友被查杀时",
        "不要被迫改投第三方冷门好人",
    ]
    for phrase in required_phrases:
        assert phrase in prompt


def test_v018_werewolf_prompt_enables_action_layer_forced_fake_seer():
    repo_root = Path(__file__).resolve().parents[1]
    prompt_path = repo_root / "strategies" / "v0.1.8" / "werewolf.txt"
    if not prompt_path.exists():
        pytest.skip("strategy prompts are optional local artifacts")

    prompt = prompt_path.read_text(encoding="utf-8")

    required_phrases = [
        "动作层强制悍跳",
        "确定性前置 fake_seer",
        "已有至少 2 名玩家发言",
        "给外置好人发查杀",
        "不只依赖模型自觉执行",
    ]
    for phrase in required_phrases:
        assert phrase in prompt


def test_v019_werewolf_prompt_optimizes_forced_fake_seer_target_selection():
    repo_root = Path(__file__).resolve().parents[1]
    prompt_path = repo_root / "strategies" / "v0.1.9" / "werewolf.txt"
    if not prompt_path.exists():
        pytest.skip("strategy prompts are optional local artifacts")

    prompt = prompt_path.read_text(encoding="utf-8")

    required_phrases = [
        "动作层目标选择优化",
        "公开自称普通村民/平民/闭眼好人",
        "低信息外置位",
        "避开公开预言家、女巫、猎人、金水、银水",
        "降低误打公开神职或金银水的风险",
    ]
    for phrase in required_phrases:
        assert phrase in prompt


def test_v0110_werewolf_prompt_lowers_forced_fake_seer_trigger_window():
    repo_root = Path(__file__).resolve().parents[1]
    prompt_path = repo_root / "strategies" / "v0.1.10" / "werewolf.txt"
    if not prompt_path.exists():
        pytest.skip("strategy prompts are optional local artifacts")

    prompt = prompt_path.read_text(encoding="utf-8")

    required_phrases = [
        "动作层触发窗口修正",
        "已有至少 1 名玩家发言",
        "第二位狼人发言也能承担 fake_seer",
        "首位发言不盲跳",
        "避免错过前置悍跳窗口",
    ]
    for phrase in required_phrases:
        assert phrase in prompt


def test_v0111_werewolf_prompt_requires_fake_seer_counterclaim_support():
    repo_root = Path(__file__).resolve().parents[1]
    prompt_path = repo_root / "strategies" / "v0.1.11" / "werewolf.txt"
    if not prompt_path.exists():
        pytest.skip("strategy prompts are optional local artifacts")

    prompt = prompt_path.read_text(encoding="utf-8")

    required_phrases = [
        "动作层队友支援修正",
        "站边队友并攻击后置对跳预言家",
        "围绕公开对跳建立票型",
        "不要继续低风险表水让悍跳狼孤立",
        "优先跟悍跳队友归票对跳预言家",
    ]
    for phrase in required_phrases:
        assert phrase in prompt


def test_v0112_werewolf_prompt_blocks_fake_reason_for_unspeaking_check_target():
    repo_root = Path(__file__).resolve().parents[1]
    prompt_path = repo_root / "strategies" / "v0.1.12" / "werewolf.txt"
    if not prompt_path.exists():
        pytest.skip("strategy prompts are optional local artifacts")

    prompt = prompt_path.read_text(encoding="utf-8")

    required_phrases = [
        "动作层验人心路修正",
        "未发言外置位",
        "不能说“他前置发言如何”",
        "外置灰位、信息压缩、首验位置收益",
        "不能编造对方前置发言状态",
    ]
    for phrase in required_phrases:
        assert phrase in prompt


def test_v0113_werewolf_prompt_requires_late_fake_seer_counterclaim():
    repo_root = Path(__file__).resolve().parents[1]
    prompt_path = repo_root / "strategies" / "v0.1.13" / "werewolf.txt"
    if not prompt_path.exists():
        pytest.skip("strategy prompts are optional local artifacts")

    prompt = prompt_path.read_text(encoding="utf-8")

    required_phrases = [
        "动作层后置补跳",
        "我方队友还没有跳预言家",
        "给公开预言家发查杀",
        "强行制造二选一票型",
        "只有当队友已经跳过预言家时，才不要重复补跳",
    ]
    for phrase in required_phrases:
        assert phrase in prompt


def test_v0114_werewolf_prompt_avoids_saved_wolf_kill_target():
    repo_root = Path(__file__).resolve().parents[1]
    prompt_path = repo_root / "strategies" / "v0.1.14" / "werewolf.txt"
    if not prompt_path.exists():
        pytest.skip("strategy prompts are optional local artifacts")

    prompt = prompt_path.read_text(encoding="utf-8")

    required_phrases = [
        "动作层刀口银水避让",
        "昨夜刀口白天仍然存活",
        "疑似女巫救起的银水",
        "强制悍跳不能给该刀口未死位发查杀",
        "不要把它作为 D1 主推目标",
    ]
    for phrase in required_phrases:
        assert phrase in prompt


def test_v0115_werewolf_prompt_requires_first_person_seer_claim_attribution():
    repo_root = Path(__file__).resolve().parents[1]
    prompt_path = repo_root / "strategies" / "v0.1.15" / "werewolf.txt"
    if not prompt_path.exists():
        pytest.skip("strategy prompts are optional local artifacts")

    prompt = prompt_path.read_text(encoding="utf-8")

    required_phrases = [
        "动作层声称归属修正",
        "一人称表达",
        "评论“Charlie 跳预言家”的玩家不被误判成预言家",
        "查杀真正一人称跳预言家的玩家",
    ]
    for phrase in required_phrases:
        assert phrase in prompt


def test_v0116_werewolf_prompt_handles_wei_checkkill_wording_and_strong_defense():
    repo_root = Path(__file__).resolve().parents[1]
    prompt_path = repo_root / "strategies" / "v0.1.16" / "werewolf.txt"
    if not prompt_path.exists():
        pytest.skip("strategy prompts are optional local artifacts")

    prompt = prompt_path.read_text(encoding="utf-8")

    required_phrases = [
        "动作层查杀措辞修正",
        "查验 X 为狼人/为狼",
        "动作层被查杀防守加强",
        "只说“对方是悍跳狼”不够",
        "必须明确不认查杀或表明自己是好人",
    ]
    for phrase in required_phrases:
        assert phrase in prompt


def test_v0117_werewolf_prompt_requires_late_fake_seer_self_checkkill_defense():
    repo_root = Path(__file__).resolve().parents[1]
    prompt_path = repo_root / "strategies" / "v0.1.17" / "werewolf.txt"
    if not prompt_path.exists():
        pytest.skip("strategy prompts are optional local artifacts")

    prompt = prompt_path.read_text(encoding="utf-8")

    required_phrases = [
        "动作层被查杀后置补跳修正",
        "给我查杀我不认，我是好人视角",
        "再对跳预言家并给对方发查杀",
        "不能只说“我对跳预言家”",
        "必须先强防守不认查杀",
    ]
    for phrase in required_phrases:
        assert phrase in prompt


def test_v0118_werewolf_prompt_requires_fake_seer_vote_guard_consolidation():
    repo_root = Path(__file__).resolve().parents[1]
    prompt_path = repo_root / "strategies" / "v0.1.18" / "werewolf.txt"
    if not prompt_path.exists():
        pytest.skip("strategy prompts are optional local artifacts")

    prompt = prompt_path.read_text(encoding="utf-8")

    required_phrases = [
        "动作层悍跳票型守卫修正",
        "验了 X 是铁狼/查出 X 是铁狼",
        "不能因为对方是预言家、金水或其他保护位就把票改到外置位",
        "支援发言必须干净站边、集中归票对跳/查杀位",
        "不能改投第三方外置位",
    ]
    for phrase in required_phrases:
        assert phrase in prompt


def test_v0119_werewolf_prompt_requires_late_fake_seer_gold_anchor_counterplay():
    repo_root = Path(__file__).resolve().parents[1]
    prompt_path = repo_root / "strategies" / "v0.1.19" / "werewolf.txt"
    if not prompt_path.exists():
        pytest.skip("strategy prompts are optional local artifacts")

    prompt = prompt_path.read_text(encoding="utf-8")

    required_phrases = [
        "动作层后置补跳反锚点修正",
        "金水是做票仓，金水本人接对身份不等于预言家为真",
        "无警长短局硬聊警徽流",
        "这是套模板，不是真预言家逻辑",
        "不要让好人用“你没警徽流”来压死你的补跳",
    ]
    for phrase in required_phrases:
        assert phrase in prompt


def test_v0120_werewolf_prompt_requires_calibrated_early_fake_seer_support():
    repo_root = Path(__file__).resolve().parents[1]
    prompt_path = repo_root / "strategies" / "v0.1.20" / "werewolf.txt"
    if not prompt_path.exists():
        pytest.skip("strategy prompts are optional local artifacts")

    prompt = prompt_path.read_text(encoding="utf-8")

    required_phrases = [
        "动作层早期支援校准",
        "非悍跳狼不能立刻铁站边队友",
        "先要求查杀位拍身份或对跳",
        "票型围绕查杀位/可能对跳位",
        "不提前铁站边",
    ]
    for phrase in required_phrases:
        assert phrase in prompt
