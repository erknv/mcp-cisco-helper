# mcp-cisco-helper

Эркинов Чынсултан, ПИ(ДОТ)-1-23

MCP сервер для задач по Cisco: расчет подсетей, VLSM, команды для VLAN, DHCP и интерфейса роутера, порты.

## Запуск

```
uv sync
uv run demo.py
```

## Через платформу (MCP Inspector)

```
npx @modelcontextprotocol/inspector .venv\Scripts\python.exe server.py
```

## NVIDIA через OpenRouter

Ключ с openrouter.ai/keys вставить в .env (OPENROUTER_API_KEY=...), потом:

```
uv run agent.py "Разбей 192.168.10.0/24 на 50, 20 и 10 хостов"
```

Берет бесплатную модель nvidia с openrouter.
