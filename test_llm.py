from langchain_openai import ChatOpenAI
from backend.core.config import settings

async def test_llm():
    llm = ChatOpenAI(
        api_key=settings.DOUBAO_API_KEY,
        base_url=settings.DOUBAO_BASE_URL,
        model=settings.DOUBAO_MODEL,
        temperature=0.8
    )
    
    try:
        response = await llm.ainvoke("你好，简单介绍下你自己")
        print("LLM调用成功：")
        print(response.content)
    except Exception as e:
        print("LLM调用失败，错误信息：")
        print(f"错误类型：{type(e).__name__}")
        print(f"错误详情：{str(e)}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_llm())
