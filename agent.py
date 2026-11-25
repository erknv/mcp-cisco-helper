"""Агент «Cisco Helper»: модель NVIDIA (через OpenRouter) + инструменты MCP.

Скрипт запускает server.py как MCP-сервер, получает список его
инструментов и передаёт его модели. Когда модель просит вызвать
инструмент, агент вызывает его через MCP и возвращает результат модели,
пока она не даст окончательный ответ.

Запуск:
    uv run agent.py "вопрос"     — один вопрос
    uv run agent.py              — диалог (выход: пустая строка или exit)

Ключ: переменная OPENROUTER_API_KEY (или файл .env рядом со скриптом).
"""

import asyncio
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai import AsyncOpenAI

HERE = Path(__file__).parent
DEFAULT_MODEL = "nvidia/nemotron-3-super-120b-a12b:free"
MAX_STEPS = 10
SYSTEM_PROMPT = (
    "Ты помощник сетевого инженера Cisco. Для расчётов подсетей, VLSM, "
    "генерации команд IOS и поиска портов всегда вызывай инструменты, "
    "а не считай в уме. Команды IOS показывай в блоке кода. Отвечай по-русски."
)


def to_openai_tool(tool) -> dict:
    """Описание инструмента MCP -> формат function calling OpenAI/OpenRouter."""
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.input_schema,
        },
    }


def tool_output(result) -> str:
    """Текст ответа инструмента MCP."""
    text = "\n".join(b.text for b in result.content if getattr(b, "text", None))
    text = text or "(пустой ответ)"
    return f"ОШИБКА: {text}" if result.is_error else text


async def ask(client, model, session, tools, messages, question) -> str:
    """Один вопрос: цикл «модель -> вызов инструментов -> модель»."""
    messages.append({"role": "user", "content": question})
    for _ in range(MAX_STEPS):
        response = await client.chat.completions.create(
            model=model, messages=messages, tools=tools
        )
        msg = response.choices[0].message
        if not msg.tool_calls:
            answer = msg.content or "(модель вернула пустой ответ)"
            messages.append({"role": "assistant", "content": answer})
            return answer

        messages.append(msg.model_dump(exclude_none=True))
        for call in msg.tool_calls:
            try:
                args = json.loads(call.function.arguments or "{}")
                output = tool_output(await session.call_tool(call.function.name, args))
            except Exception as error:  # ошибку отдаём модели, чтобы она исправилась
                args, output = call.function.arguments, f"ОШИБКА: {error}"
            print(f"  [MCP] -> {call.function.name}({json.dumps(args, ensure_ascii=False)})")
            print("  [MCP] <- " + output.replace("\n", "\n         "))
            messages.append({"role": "tool", "tool_call_id": call.id, "content": output})
    return f"Модель не дала ответ за {MAX_STEPS} шагов."


async def main() -> int:
    load_dotenv(HERE / ".env")
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("Не задан OPENROUTER_API_KEY. Скопируйте .env.example в .env "
              "и вставьте ключ с https://openrouter.ai/keys", file=sys.stderr)
        return 1

    model = os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL)
    client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
    server = StdioServerParameters(command=sys.executable, args=[str(HERE / "server.py")])

    async with stdio_client(server) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        mcp_tools = (await session.list_tools()).tools
        tools = [to_openai_tool(t) for t in mcp_tools]
        print(f"Модель:          {model} (OpenRouter)")
        print(f"Инструменты MCP: {', '.join(t.name for t in mcp_tools)}\n")

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if len(sys.argv) > 1:
            question = " ".join(sys.argv[1:])
            print(f"Вопрос: {question}\n")
            print(f"\nОтвет:\n{await ask(client, model, session, tools, messages, question)}")
            return 0

        while True:
            try:
                question = input("Вы> ").strip()
            except EOFError:
                break
            if question.lower() in ("", "exit", "quit", "выход"):
                break
            print(f"\nАгент>\n{await ask(client, model, session, tools, messages, question)}\n")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
