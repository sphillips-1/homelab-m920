"""Idempotent S3 PutBucket using AWS SigV4, without extra dependencies."""
from datetime import datetime, timezone
import hashlib
import hmac
import os
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def create_bucket():
    now = datetime.now(timezone.utc)
    stamp, day = now.strftime('%Y%m%dT%H%M%SZ'), now.strftime('%Y%m%d')
    host, path = 'minio:9000', '/' + os.environ['S3_BUCKET_NAME']
    empty = hashlib.sha256(b'').hexdigest()
    headers = f'host:{host}\nx-amz-content-sha256:{empty}\nx-amz-date:{stamp}\n'
    names = 'host;x-amz-content-sha256;x-amz-date'
    canonical = f'PUT\n{path}\n\n{headers}\n{names}\n{empty}'
    scope = f'{day}/us-east-1/s3/aws4_request'
    to_sign = f'AWS4-HMAC-SHA256\n{stamp}\n{scope}\n{hashlib.sha256(canonical.encode()).hexdigest()}'
    key = ('AWS4' + os.environ['MINIO_ROOT_PASSWORD']).encode()
    for value in (day, 'us-east-1', 's3', 'aws4_request'):
        key = hmac.new(key, value.encode(), hashlib.sha256).digest()
    signature = hmac.new(key, to_sign.encode(), hashlib.sha256).hexdigest()
    auth = (f'AWS4-HMAC-SHA256 Credential={os.environ["MINIO_ROOT_USER"]}/{scope}, '
            f'SignedHeaders={names}, Signature={signature}')
    request = Request('http://' + host + path, method='PUT', data=b'', headers={
        'Authorization': auth, 'x-amz-date': stamp, 'x-amz-content-sha256': empty})
    try:
        with urlopen(request, timeout=5) as response:
            assert response.status == 200
    except HTTPError as error:
        if error.code != 409 or b'BucketAlreadyOwnedByYou' not in error.read():
            raise


if __name__ == '__main__':
    for attempt in range(60):
        try:
            create_bucket()
            print('Readest private S3 bucket is ready.')
            break
        except Exception:
            if attempt == 59:
                raise
            time.sleep(2)
