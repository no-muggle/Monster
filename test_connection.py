"""Quick connectivity test for SMS Sync.

Run this on the PC to verify the port is accessible.
Also run the printed command on another device to test from that device.
"""

import socket
import sys


def test_local(host: str, port: int) -> bool:
    """Test if we can connect to the server from localhost."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3)
        s.connect((host, port))
        s.close()
        return True
    except Exception as e:
        print(f"  FAIL: {e}")
        return False


def main():
    from src.network.lan_ip import get_lan_ip, get_all_local_ips

    port = 9876
    host = get_lan_ip()
    all_ips = get_all_local_ips()

    print("=" * 60)
    print("SMS Sync — Connection Test")
    print("=" * 60)
    print(f"\nDetected LAN IP: {host}")
    print(f"All IPs: {', '.join(all_ips)}")
    print(f"Port: {port}")
    print()

    # Test 1: localhost
    print("1. Testing localhost connection...")
    if test_local("127.0.0.1", port):
        print("   OK — server is running")
    else:
        print("   Server may not be running. Start it first:")
        print("   python -m src.main")

    # Test 2: LAN IP
    print(f"\n2. Testing LAN IP ({host}) connection...")
    if test_local(host, port):
        print("   OK — port is reachable on LAN IP")
    else:
        print("   FAIL — port NOT reachable on LAN IP!")
        print("   This usually means Windows Firewall is blocking.")
        print("   Run this command as Administrator:")
        print(f'   netsh advfirewall firewall add rule name="SMS Sync" dir=in action=allow protocol=TCP localport={port}')
        return

    # Test 3: Print command for phone testing
    print(f"\n3. From your Android phone, test with:")
    print(f"   - Open browser and go to: http://{host}:{port}")
    print(f"   - If it loads (even with an error page), the network is OK")
    print(f"\n   Or from another PC on the same WiFi:")
    print(f'   python -c "import socket; s=socket.socket(); s.settimeout(3); s.connect((\'{host}\', {port})); print(\'OK\'); s.close()"')

    print("\n" + "=" * 60)
    print("If all tests pass but phone still can't connect:")
    print("1. Check router AP/client isolation setting")
    print("2. Try turning off mobile data on phone (force WiFi)")
    print("3. Check if PC and phone are on same subnet")
    print(f"   PC: {host}")
    print(f"   Phone WiFi settings should show a similar IP")


if __name__ == "__main__":
    main()
