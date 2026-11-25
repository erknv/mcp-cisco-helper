# mcp-cisco-helper

**Студент:** Эркинов Чынсултан, ПИ(ДОТ)-1-23
**Дисциплина:** Разработка и поддержка компьютерных сетей CISCO

MCP-сервер с инструментами для задач по сетям Cisco и агент, который
пользуется ими через модель NVIDIA (Nemotron) на OpenRouter.

**MCP (Model Context Protocol)** — открытый протокол, по которому нейросеть
вызывает внешние инструменты. Сервер описывает свои инструменты, клиент
(Claude, агент на OpenRouter и т. д.) передаёт их модели, а модель сама
решает, какой инструмент вызвать и с какими аргументами.

## Инструменты сервера

| Инструмент                | Что делает                                                        |
|---------------------------|-------------------------------------------------------------------|
| `subnet_calc`             | параметры подсети: сеть, маска, wildcard, broadcast, хосты        |
| `vlsm_plan`               | разбиение сети на подсети по числу хостов (VLSM)                  |
| `vlan_config`             | команды Cisco IOS для VLAN и access-портов коммутатора            |
| `dhcp_pool_config`        | команды Cisco IOS для DHCP-пула на маршрутизаторе                 |
| `router_interface_config` | команды Cisco IOS для IP-адреса интерфейса маршрутизатора         |
| `port_lookup`             | справочник портов: SSH, DNS, DHCP, HTTP и др.                     |

## Файлы проекта

| Файл           | Назначение                                                    |
|----------------|---------------------------------------------------------------|
| `server.py`    | MCP-сервер (транспорт stdio)                                  |
| `agent.py`     | агент: модель NVIDIA через OpenRouter + инструменты сервера   |
| `demo.py`      | проверка сервера из терминала без нейросети                   |
| `.env.example` | шаблон файла с ключом OpenRouter                              |

## Установка

Нужен [uv](https://docs.astral.sh/uv/) (менеджер Python-проектов).

```sh
git clone https://github.com/erknv/mcp-cisco-helper.git
cd mcp-cisco-helper
uv sync
```

## 1. Работа через терминал

Проверка сервера настоящим MCP-клиентом, без нейросети:

```sh
uv run demo.py
```

Скрипт подключается к `server.py`, выводит список инструментов и вызывает
каждый из них с примером.

Подключение к Claude Code (агент в терминале):

```sh
claude mcp add cisco-helper -- uv run --directory /полный/путь/к/mcp-cisco-helper server.py
claude
```

В чате: «разбей 192.168.10.0/24 по VLSM на 50, 20 и 10 хостов».

## 2. Работа через платформу (Claude Desktop)

Settings → Developer → Edit Config, в файл `claude_desktop_config.json`
добавить:

```json
{
  "mcpServers": {
    "cisco-helper": {
      "command": "uv",
      "args": ["run", "--directory", "C:\\полный\\путь\\к\\mcp-cisco-helper", "server.py"]
    }
  }
}
```

После перезапуска Claude Desktop инструменты `cisco-helper` появятся в меню
инструментов чата.

## 3. NVIDIA NIM через OpenRouter (API-ключ)

1. Создайте ключ на <https://openrouter.ai/keys>.
2. Скопируйте `.env.example` в `.env` и вставьте ключ в `OPENROUTER_API_KEY`.
3. Запустите один вопрос или диалог:

```sh
uv run agent.py "Разбей 192.168.10.0/24 на подсети для 50, 20 и 10 хостов"
uv run agent.py
```

По умолчанию используется бесплатная модель
`nvidia/nemotron-3-super-120b-a12b:free`, другую можно задать в
`OPENROUTER_MODEL`. Агент печатает каждый вызов инструмента
(`[MCP] -> ...`) и его результат (`[MCP] <- ...`), так видно, что модель
действительно работает через MCP.

## Как это работает

```
вопрос -> agent.py -> модель NVIDIA (OpenRouter)
                        | просит вызвать инструмент
                        v
          agent.py -> MCP (stdio) -> server.py -> результат
                        |
                        v
            модель формирует ответ по результату
```

## Скриншоты

Скриншоты трёх способов запуска сданы в Google Classroom.
