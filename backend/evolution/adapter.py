from typing import Dict, List, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from backend.core.config import settings


class OptimizedPrompt(BaseModel):
    optimized_prompt: str = Field(description="优化后的Prompt文本")
    reasoning: str = Field(description="优化的理由和思路")
    key_changes: List[str] = Field(description="关键变更点列表")


class Adapter:
    def __init__(self):
        self.llm = ChatOpenAI(
            api_key=settings.DOUBAO_API_KEY,
            base_url=settings.DOUBAO_BASE_URL,
            model=settings.DOUBAO_MODEL,
            temperature=0.7,
        )
        self.code_llm = ChatOpenAI(
            api_key=settings.DOUBAO_API_KEY,
            base_url=settings.DOUBAO_BASE_URL,
            model=settings.DOUBAO_CODE_MODEL,
            temperature=0.3,
        )

    def optimize_prompt(self, original_prompt: str, role: str, 
                   analysis: Dict[str, Any]) -> Dict[str, Any]:
        suggestions = self._generate_suggestions(role, analysis)
        optimized = self._apply_suggestions(original_prompt, role, suggestions)
        return {
            "original": original_prompt,
            "optimized": optimized.get("optimized_prompt", original_prompt),
            "reasoning": optimized.get("reasoning", ""),
            "key_changes": optimized.get("key_changes", []),
        }

    def optimize_all_prompts(self, prompts: Dict[str, str], 
                        aggregate_analysis: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        results = {}
        for role, prompt in prompts.items():
            results[role] = self.optimize_prompt(prompt, role, aggregate_analysis)
        return results

    def _generate_suggestions(self, role: str, analysis: Dict[str, Any]) -> List[str]:
        suggestions = []
        
        role_specific_suggestions = {
            "werewolf": [
                "优化首刀策略，优先选择预言家和女巫",
                "改进隐藏身份的发言技巧",
                "增强狼队友之间的配合",
                "优化自爆时机的判断",
            ],
            "seer": [
                "优化首验策略，提高首验中狼率",
                "改进跳身份的时机选择",
                "优化警徽流设计",
                "增强发言的说服力",
            ],
            "witch": [
                "优化解药使用策略，优先救预言家",
                "改进毒药使用策略，精准毒杀狼人",
                "优化隐藏身份的技巧",
            ],
            "hunter": [
                "优化开枪时机的判断",
                "改进遗言的策略",
                "增强对场上局势的分析能力",
            ],
            "villager": [
                "优化投票策略，提高投中狼人的概率",
                "改进发言技巧，避免被抗推",
                "增强对场上局势的分析能力",
            ],
        }
        
        suggestions.extend(role_specific_suggestions.get(role, []))
        
        win_rate = analysis.get("werewolf_win_rate", 0.5)
        if role == "werewolf" and win_rate < 0.5:
            suggestions.append("当前狼人胜率偏低，需要更激进的策略")
        elif role != "werewolf" and win_rate > 0.6:
            suggestions.append("当前好人胜率偏低，需要加强防守策略")
        
        return suggestions

    def _apply_suggestions(self, original_prompt: str, role: str, 
                      suggestions: List[str]) -> Dict[str, Any]:
        parser = JsonOutputParser(pydantic_object=OptimizedPrompt)
        
        suggestion_text = "\n".join(f"- {s}" for s in suggestions)
        
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", """你是一个专业的Prompt优化专家。你的任务是基于分析结果和优化建议，
改进狼人杀游戏中{role}角色的系统Prompt。

请按照以下要求优化：
1. 保留原Prompt的核心内容和结构
2. 基于优化建议进行改进
3. 输出必须是JSON格式，包含optimized_prompt、reasoning和key_changes三个字段
4. key_changes应该列出具体的改进点

{format_instructions}
"""),
            ("user", """原始Prompt：
{original_prompt}

优化建议：
{suggestions}

请优化这个Prompt。"""),
        ])
        
        chain = prompt_template | self.llm | parser
        
        try:
            result = chain.invoke({
                "role": role,
                "original_prompt": original_prompt,
                "suggestions": suggestion_text,
                "format_instructions": parser.get_format_instructions(),
            })
            return result.model_dump()
        except Exception as e:
            return {
                "optimized_prompt": original_prompt,
                "reasoning": f"优化失败，使用原Prompt：{str(e)}",
                "key_changes": [],
            }

    def create_tactical_prompt(self, role: str, tactic_type: str) -> str:
        tactics = {
            "werewolf": {
                "aggressive": """你是一个激进的狼人，采取积极进攻策略：
1. 首日就跳预言家，给好人发查杀
2. 积极煽动，引导投票
3. 必要时果断自爆保护队友
""",
                "conservative": """你是一个保守的狼人，采取隐藏策略：
1. 不主动跳身份，伪装成平民
2. 跟风投票，避免暴露
3. 尽量存活到后期
""",
            },
            "seer": {
                "aggressive": """你是一个激进的预言家：
1. 首日必须跳身份，报出查验结果
2. 积极带队，组织好人投票
3. 留下清晰的警徽流
""",
                "conservative": """你是一个保守的预言家：
1. 先隐藏身份观察局势
2. 第二天或第三天再跳
3. 确保自身安全的前提下带队
""",
            },
        }
        
        role_tactics = tactics.get(role, {})
        return role_tactics.get(tactic_type, "")

    def merge_prompts(self, prompts: List[str], weights: Optional[List[float]] = None) -> str:
        if not prompts:
            return ""
        if len(prompts) == 1:
            return prompts[0]
        
        if not weights:
            weights = [1.0 / len(prompts)] * len(prompts)
        
        merged_parts = []
        for i, prompt in enumerate(prompts):
            weight = weights[i]
            if weight > 0:
                merged_parts.append(f"## 策略{i+1} (权重: {weight:.2f})\n{prompt}")
        
        merged_prompt = "\n\n".join(merged_parts)
        merged_prompt += "\n\n## 综合策略\n请综合以上策略，根据实际游戏情况灵活运用。"
        
        return merged_prompt

    def create_evolution_summary(self, old_version: str, new_version: str, 
                            changes: List[str], analysis: Dict[str, Any]) -> str:
        summary = f"""
# 策略进化报告

## 版本信息
- 旧版本: {old_version}
- 新版本: {new_version}
- 更新时间: {analysis.get('timestamp', 'unknown')}

## 主要变更
{chr(10).join(f'- {change}' for change in changes)}

## 分析依据
- 分析游戏数: {analysis.get('total_games', 0)}
- 狼人胜率变化: {analysis.get('werewolf_win_rate', 0):.2%}

## 预期效果
希望通过本次优化，提升Agent的游戏表现和胜率。
"""
        return summary
