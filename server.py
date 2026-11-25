"""MCP-сервер «Cisco Helper».

Даёт нейросети инструменты для задач из курса по сетям Cisco:
расчёт подсети, разбиение сети по VLSM, генерация команд Cisco IOS
(VLAN, DHCP, интерфейс маршрутизатора) и справочник сетевых портов.

Автор: Эркинов Чынсултан, ПИ(ДОТ)-1-23
Запуск (транспорт stdio):  uv run server.py
"""

import ipaddress

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

mcp = MCPServer("cisco-helper")

# Справочник известных портов (порт -> протокол, служба)
PORTS = {
    20: ("TCP", "FTP (данные)"),
    21: ("TCP", "FTP (управление)"),
    22: ("TCP", "SSH"),
    23: ("TCP", "Telnet"),
    25: ("TCP", "SMTP"),
    53: ("TCP/UDP", "DNS"),
    67: ("UDP", "DHCP (сервер)"),
    68: ("UDP", "DHCP (клиент)"),
    69: ("UDP", "TFTP"),
    80: ("TCP", "HTTP"),
    110: ("TCP", "POP3"),
    123: ("UDP", "NTP"),
    143: ("TCP", "IMAP"),
    161: ("UDP", "SNMP"),
    443: ("TCP", "HTTPS"),
    514: ("UDP", "Syslog"),
    520: ("UDP", "RIP"),
    3389: ("TCP", "RDP"),
}


def _net(cidr: str) -> ipaddress.IPv4Network:
    try:
        return ipaddress.IPv4Network(cidr, strict=False)
    except ValueError as error:
        raise ToolError(f"некорректная сеть «{cidr}»: {error}") from None


@mcp.tool()
def subnet_calc(cidr: str) -> dict:
    """Рассчитать параметры IPv4-подсети.

    cidr — адрес с префиксом или маской: "192.168.1.10/26"
    или "192.168.1.10/255.255.255.192".
    Возвращает адрес сети, маску, wildcard (для ACL и OSPF),
    broadcast, диапазон хостов и их количество.
    """
    net = _net(cidr)
    small = net.prefixlen >= 31
    return {
        "network": f"{net.network_address}/{net.prefixlen}",
        "netmask": str(net.netmask),
        "wildcard": str(net.hostmask),
        "broadcast": str(net.broadcast_address),
        "first_host": str(net.network_address if small else net.network_address + 1),
        "last_host": str(net.broadcast_address if small else net.broadcast_address - 1),
        "usable_hosts": net.num_addresses if small else net.num_addresses - 2,
    }


@mcp.tool()
def vlsm_plan(network: str, hosts: list[int]) -> list[dict]:
    """Разбить сеть на подсети разного размера (VLSM).

    network — исходная сеть, например "192.168.10.0/24".
    hosts — сколько хостов нужно в каждой подсети, например [50, 20, 10, 2].
    Подсети выделяются от большей к меньшей, без пересечений.
    """
    base = _net(network)
    cursor = int(base.network_address)
    plan = []
    for need in sorted(hosts, reverse=True):
        if need < 1:
            raise ToolError("число хостов должно быть больше нуля")
        prefix = 32
        while (2 ** (32 - prefix)) - 2 < need:
            prefix -= 1
        size = 2 ** (32 - prefix)
        cursor = (cursor + size - 1) // size * size  # выравнивание по границе блока
        sub = ipaddress.IPv4Network((cursor, prefix))
        if not sub.subnet_of(base):
            raise ToolError(f"в сеть {base} не помещается подсеть на {need} хостов")
        plan.append({
            "need_hosts": need,
            "subnet": str(sub),
            "netmask": str(sub.netmask),
            "gateway": str(sub.network_address + 1),
            "range": f"{sub.network_address + 1} - {sub.broadcast_address - 1}",
            "broadcast": str(sub.broadcast_address),
            "usable_hosts": size - 2,
        })
        cursor += size
    return plan


@mcp.tool()
def vlan_config(vlans: dict[str, str], access_ports: dict[str, int]) -> str:
    """Сгенерировать команды Cisco IOS для VLAN на коммутаторе.

    vlans — номер VLAN -> имя, например {"10": "SALES", "20": "IT"}.
    access_ports — порт -> VLAN, например {"FastEthernet0/1": 10}.
    """
    lines = ["enable", "configure terminal"]
    for vid, name in vlans.items():
        lines += [f"vlan {int(vid)}", f" name {name}", "exit"]
    for port, vid in access_ports.items():
        if str(vid) not in vlans:
            raise ToolError(f"VLAN {vid} для порта {port} не описан в vlans")
        lines += [
            f"interface {port}",
            " switchport mode access",
            f" switchport access vlan {int(vid)}",
            "exit",
        ]
    lines += ["end", "write memory"]
    return "\n".join(lines)


@mcp.tool()
def dhcp_pool_config(pool_name: str, network: str, gateway: str,
                     dns: str = "8.8.8.8", excluded: int = 10) -> str:
    """Сгенерировать команды Cisco IOS для DHCP-пула на маршрутизаторе.

    network — сеть пула ("192.168.1.0/24"), gateway — шлюз по умолчанию,
    dns — DNS-сервер, excluded — сколько первых адресов не раздавать
    (под шлюз и серверы).
    """
    net = _net(network)
    if ipaddress.IPv4Address(gateway) not in net:
        raise ToolError(f"шлюз {gateway} не лежит в сети {net}")
    first = net.network_address + 1
    last_excl = net.network_address + max(excluded, 1)
    return "\n".join([
        "enable",
        "configure terminal",
        f"ip dhcp excluded-address {first} {last_excl}",
        f"ip dhcp pool {pool_name}",
        f" network {net.network_address} {net.netmask}",
        f" default-router {gateway}",
        f" dns-server {dns}",
        "exit",
        "end",
        "write memory",
    ])


@mcp.tool()
def router_interface_config(interface: str, ip_with_prefix: str,
                            description: str = "") -> str:
    """Сгенерировать команды Cisco IOS для интерфейса маршрутизатора.

    interface — имя, например "GigabitEthernet0/0".
    ip_with_prefix — адрес интерфейса с префиксом, например "192.168.1.1/24".
    """
    iface = ipaddress.IPv4Interface(ip_with_prefix)
    lines = ["enable", "configure terminal", f"interface {interface}"]
    if description:
        lines.append(f" description {description}")
    lines += [
        f" ip address {iface.ip} {iface.netmask}",
        " no shutdown",
        "end",
        "write memory",
    ]
    return "\n".join(lines)


@mcp.tool()
def port_lookup(query: str) -> list[dict]:
    """Найти сетевой порт по номеру или службу по названию.

    query — номер порта ("22") или название службы ("dhcp", "https").
    """
    q = query.strip().lower()
    found = []
    for port, (proto, service) in PORTS.items():
        if q == str(port) or q in service.lower():
            found.append({"port": port, "protocol": proto, "service": service})
    if not found:
        return [{"result": f"порт или служба «{query}» нет в справочнике"}]
    return found


if __name__ == "__main__":
    mcp.run()
