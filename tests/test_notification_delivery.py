"""Optional Docker integration test using isolated, disposable services and dummy credentials."""
import subprocess
import uuid


def main():
    suffix = uuid.uuid4().hex[:10]
    network = 'notification-test-' + suffix
    ntfy = 'ntfy-test-' + suffix
    apprise = 'apprise-test-' + suffix

    def docker(*args):
        return subprocess.check_output(['docker', *args], stderr=subprocess.STDOUT, text=True)

    try:
        docker('network', 'create', '--internal', network)
        docker('run', '-d', '--name', ntfy, '--network', network,
               '--network-alias', 'ntfy-test',
               '-e', 'NTFY_AUTH_FILE=/tmp/auth.db', '-e', 'NTFY_CACHE_FILE=/tmp/cache.db',
               '-e', 'NTFY_AUTH_DEFAULT_ACCESS=deny-all', 'binwiederhier/ntfy:v2.29.0', 'serve')
        docker('run', '-d', '--name', apprise, '--network', network,
               '--network-alias', 'apprise-test', '-e', 'APPRISE_STATEFUL_MODE=disabled',
               'caronc/apprise:2.0.0')
        for username, permission in [('publisher', 'write-only'), ('reader', 'read-only')]:
            docker('exec', '-e', 'NTFY_PASSWORD=integration-dummy-password', ntfy,
                   'ntfy', 'user', 'add', '--ignore-exists', username)
            docker('exec', ntfy, 'ntfy', 'access', username, 'test-books', permission)
        probe = r'''
import base64,json,time
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError

def call(url, data=None, user=None):
    headers={'Content-Type':'application/json'}
    if user:
        headers['Authorization']='Basic '+base64.b64encode((user+':integration-dummy-password').encode()).decode()
    with urlopen(Request(url, data=None if data is None else json.dumps(data).encode(),headers=headers),timeout=5) as response:
        return response.read().decode()

for attempt in range(40):
    try:
        call('http://apprise-test:8000/status')
        break
    except (HTTPError,URLError,TimeoutError):
        time.sleep(1)
else:
    raise RuntimeError('Apprise did not become ready')

result=call('http://apprise-test:8000/notify/',{
    'urls':'ntfy://publisher:integration-dummy-password@ntfy-test:80/test-books',
    'title':'Integration test', 'body':'Disposable notification test', 'format':'text'})
print('Apprise response:',result)
for attempt in range(20):
    data=call('http://ntfy-test/test-books/json?poll=1&since=all',user='reader')
    if 'Disposable notification test' in data:
        break
    time.sleep(1)
else:
    raise RuntimeError('Message not delivered')
for user,data in [(None,None),('publisher',None),('reader',{'topic':'test-books','message':'Must be denied'})]:
    try:
        call('http://ntfy-test/test-books/json?poll=1' if data is None else 'http://ntfy-test/',data,user)
    except HTTPError as error:
        assert error.code in (401,403),error.code
    else:
        raise RuntimeError('Access control failed')
print('PASS: Apprise delivery, authenticated reading, anonymous denial, publisher read denial, reader write denial')
'''
        result = subprocess.run(['docker', 'run', '--rm', '-i', '--network', network,
                                 'python:3.13.7-alpine', 'python', '-'],
                                input=probe, text=True, capture_output=True)
        print(result.stdout)
        if result.returncode:
            print(result.stderr)
            raise SystemExit(result.returncode)
    finally:
        for container in (apprise, ntfy):
            subprocess.run(['docker', 'rm', '-f', container], capture_output=True)
        subprocess.run(['docker', 'network', 'rm', network], capture_output=True)


if __name__ == '__main__':
    main()
