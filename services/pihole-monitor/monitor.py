"""Pi-hole DNS outage monitor. Only transition notifications are sent."""
import argparse
import json
import os
from pathlib import Path
import secrets
import socket
import struct
import tempfile
import time
import urllib.request

DATA = Path(os.getenv('STATE_DIR', '/data'))
WEBHOOK = Path(os.getenv('WEBHOOK_FILE', '/run/secrets/discord-webhook.url'))
DNS_SERVER = os.getenv('PIHOLE_IP', '192.168.4.75')
INTERVAL = int(os.getenv('CHECK_INTERVAL', '60'))
THRESHOLD = int(os.getenv('FAILURE_THRESHOLD', '3'))


def dns_healthy(server=DNS_SERVER):
    """Require a matching, successful DNS answer, not just a reachable host."""
    ident = secrets.randbelow(65536)
    name = b'\x07example\x03com\x00'
    query = struct.pack('!6H', ident, 0x100, 1, 0, 0, 0) + name + struct.pack('!2H', 1, 1)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(5)
            sock.connect((server, 53))
            sock.send(query)
            reply = sock.recv(4096)
        rid, flags, questions, answers, _, _ = struct.unpack('!6H', reply[:12])
        return (rid == ident and bool(flags & 0x8000) and not flags & 0x0200
                and flags & 0xF == 0 and questions == 1 and answers > 0)
    except (OSError, struct.error):
        return False


def notify(message):
    # Never log URLs or exception text: webhook URLs contain credentials.
    url = WEBHOOK.read_text().strip()
    body = json.dumps({'content': message, 'allowed_mentions': {'parse': []}}).encode()
    request = urllib.request.Request(url, data=body, headers={
        'Content-Type': 'application/json', 'User-Agent': 'Homelab-Pihole-Monitor/1.0'})
    with urllib.request.urlopen(request, timeout=15) as response:
        if response.status not in (200, 204):
            raise RuntimeError('Discord rejected notification')


def step(state, healthy, send=notify):
    state['failures'] = 0 if healthy else min(state.get('failures', 0) + 1, THRESHOLD)
    notified = state.get('outage_notified', False)
    if not healthy and state['failures'] >= THRESHOLD and not notified:
        send(f'🔴 Pi-hole DNS outage: {DNS_SERVER} failed {THRESHOLD} consecutive checks from M920Q.')
        state['outage_notified'] = True
    elif healthy and notified:
        send(f'🟢 Pi-hole DNS recovered: {DNS_SERVER} is answering DNS queries from M920Q.')
        state['outage_notified'] = False
    return state


def save_state(state):
    DATA.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=DATA, prefix='.state-')
    try:
        with os.fdopen(fd, 'w') as output:
            json.dump(state, output)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, DATA / 'state.json')
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--test-notifications', action='store_true')
    args = parser.parse_args()
    if args.check:
        healthy = dns_healthy()
        print('DNS check: ' + ('healthy' if healthy else 'failed'), flush=True)
        raise SystemExit(0 if healthy else 1)
    if args.test_notifications:
        notify('🧪 TEST: Simulated Pi-hole DNS outage. The live DNS service has not been interrupted.')
        notify('🧪 TEST: Simulated Pi-hole DNS recovery. Discord notification delivery is working.')
        print('Outage and recovery test messages delivered.', flush=True)
        return
    if INTERVAL < 1 or THRESHOLD < 1:
        raise ValueError('Check interval and failure threshold must be positive')
    WEBHOOK.read_text()  # Fail immediately if the credential is missing.
    state_path = DATA / 'state.json'
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    while True:
        started = time.monotonic()
        healthy = dns_healthy()
        try:
            step(state, healthy)
        except Exception as error:
            print(f'Notification failed ({type(error).__name__}); retrying next check.', flush=True)
        state['last_check'] = time.time()
        state['dns_healthy'] = healthy
        save_state(state)
        print('DNS check: ' + ('healthy' if healthy else 'failed'), flush=True)
        time.sleep(max(0, INTERVAL - (time.monotonic() - started)))


if __name__ == '__main__':
    main()
