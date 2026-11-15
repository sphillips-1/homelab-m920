"""Write the CYD's Wi-Fi and host configuration to a PC-mounted microSD card."""
import argparse
import getpass
import ipaddress
from pathlib import Path
import re
from urllib.parse import urlsplit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("card", type=Path, help="root of the mounted microSD card")
    parser.add_argument("--host", required=True, help="example http://192.168.1.10:8784")
    parser.add_argument("--token-file", required=True, type=Path, help="host cache cyd-token.txt")
    args = parser.parse_args()
    if not args.card.is_dir():
        parser.error("microSD root is unavailable")
    host = urlsplit(args.host)
    try:
        ip = ipaddress.IPv4Address(host.hostname)
        valid = any(ip in ipaddress.ip_network(block) for block in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))
        if (not valid or host.scheme != "http" or not host.port or host.username or host.password or
                host.path not in ("", "/") or host.query or host.fragment):
            raise ValueError
    except (ValueError, TypeError):
        parser.error("use the host's private IPv4 address and port")
    key = args.token_file.read_text().strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}", key):
        parser.error("host token file is invalid")
    ssid = input("2.4 GHz Wi-Fi network name: ")
    password = getpass.getpass("Wi-Fi password: ")
    if not 1 <= len(ssid.encode()) <= 32 or len(password.encode()) > 63:
        parser.error("invalid Wi-Fi network name or password length")
    temporary = args.card / "network.part"
    temporary.write_text("\n".join((ssid, password, f"http://{host.netloc}", key, "")), encoding="utf-8")
    temporary.replace(args.card / "network.txt")
    print("Configuration saved. Eject the card, return it to the CYD and restart.")


if __name__ == "__main__":
    main()
