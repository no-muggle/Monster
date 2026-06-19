"""LAN IP detection utility.

Uses the UDP socket trick to determine which interface would be used
for local network traffic, avoiding virtual adapters and VPNs.
"""

import socket


def get_lan_ip() -> str:
    """Get the IPv4 address of the primary LAN interface.

    Connects a UDP socket to a non-routable address to determine
    which interface would be used for local network traffic.
    No actual packets are sent.

    Returns:
        The LAN IPv4 address, or "127.0.0.1" if detection fails.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # 10.255.255.255 is a non-routable TEST-NET address.
        # This connect() call doesn't send any data — it just
        # tells the kernel to pick a source address.
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
    except OSError:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def get_all_local_ips() -> list[str]:
    """Get all non-loopback IPv4 addresses on this machine.

    Useful for showing the user options when multiple interfaces exist.

    Returns:
        List of IPv4 addresses (sorted, excluding 127.x.x.x).
    """
    ips = []
    hostname = socket.gethostname()
    try:
        addrs = socket.getaddrinfo(hostname, None, socket.AF_INET)
        for addr in addrs:
            ip = addr[4][0]
            if not ip.startswith("127.") and ip not in ips:
                ips.append(ip)
    except socket.gaierror:
        pass
    return sorted(ips)
