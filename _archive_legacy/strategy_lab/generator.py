"""V1.1 AI 策略自动生成器：根据市场环境生成 A 股量化策略。

说明：本项目统一使用 OpenAI Responses API（用户硬约束），
模型名与 API Key 只从 .env 读取（OPENAI_MODEL / OPENAI_API_KEY）。
"""
from core.config import get_openai_client, get_openai_model


def create_strategy(market):
    client = get_openai_client()
    model = get_openai_model()
    prompt = f"""
根据市场环境：
{market}
设计一个A股量化策略。

输出：
买入条件
卖出条件
风险控制

"""
    response = client.responses.create(
        model=model,
        input=prompt,
    )
    return response.output_text
