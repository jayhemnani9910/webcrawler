"""Simple integration check that verifies OTSD and IPFS endpoints are reachable.

This script will:
- query the OTSD simulator /ots/submit with a test payload and fetch the proof
- query the IPFS API /api/v0/version to ensure the daemon responds
"""
import requests
import time
import sys
import os

def check_otsd(base='http://127.0.0.1:8080'):
    print('Checking OTSD at', base)
    r = requests.post(base + '/ots/submit', data=b'test-proof')
    if r.status_code not in (200,201):
        print('OTSD submit failed', r.status_code, r.text)
        return False
    pid = r.json().get('id')
    if not pid:
        print('OTSD missing id')
        return False
    pr = requests.get(base + '/ots/proof/' + pid)
    if pr.status_code != 200:
        print('Failed to fetch proof', pr.status_code)
        return False
    print('OTSD ok, proof size', len(pr.content))
    return True

def check_ipfs(base='http://127.0.0.1:5001'):
    print('Checking IPFS API at', base)
    try:
        r = requests.post(base + '/api/v0/version')
    except Exception as e:
        print('IPFS request failed', e)
        return False
    if r.status_code != 200:
        print('IPFS API returned', r.status_code, r.text)
        return False
    print('IPFS ok:', r.json().get('Version'))
    return True

def main():
    # give services a moment to come up
    time.sleep(2)
    if not check_otsd():
        print('OTSD check failed')
        sys.exit(2)
    skip_ipfs = bool(int(os.environ.get('SKIP_IPFS', '0')))
    if skip_ipfs:
        print('Skipping IPFS check (SKIP_IPFS=1)')
        print('Integration checks passed (partial)')
        return
    if not check_ipfs():
        print('IPFS check failed')
        sys.exit(3)
    print('Integration checks passed')

if __name__ == '__main__':
    main()
