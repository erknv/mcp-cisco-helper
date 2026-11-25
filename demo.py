"""Проверка MCP-сервера из терминала без нейросети.

Запускает server.py как настоящий MCP-клиент, выводит список
инструментов и вызывает каждый из них с примером.

Запуск:  uv run demo.py
"""

import asyncio
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

HERE = Path(__file__).parent
EXAMPLES = [
    ("subnet_calc", {"cidr": "192.168.1.10/26"}),
    ("vlsm_plan", {"network": "192.168.10.0/24", "hosts": [50, 20, 10, 2]}),
    ("vlan_config", {"vlans": {"10": "SALES", "20": "IT"},
                     "access_ports": {"FastEthernet0/1": 10, "FastEthernet0/3": 20}}),
    ("dhcp_pool_config", {"pool_name": "LAN", "network": "192.168.1.0/24",
                          "gateway": "192.168.1.1"}),
    ("router_interface_config", {"interface": "GigabitEthernet0/0",
                                 "ip_with_prefix": "192.168.1.1/24"}),
    ("port_lookup", {"query": "dhcp"}),
]


async def main() -> None:
    server = StdioServerParameters(command=sys.executable, args=[str(HERE / "server.py")])
    async with stdio_client(server) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        tools = (await session.list_tools()).tools
        print(f"Сервер cisco-helper, инструментов: {len(tools)}")
        for tool in tools:
            print(f"  - {tool.name}: {(tool.description or '').splitlines()[0]}")
        for name, args in EXAMPLES:
            result = await session.call_tool(name, args)
            print(f"\n=== {name}({args})")
            print("\n".join(b.text for b in result.content if getattr(b, "text", None)))


if __name__ == "__main__":
    asyncio.run(main())
