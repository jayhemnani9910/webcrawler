import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.merkle_distributed import merge_forests


def test_merge_deterministic_and_conflict():
    a = {'nodes': [
        {'node_hash': 'aa', 'payload': 'one'},
        {'node_hash': 'bb', 'payload': 'two'}
    ]}
    b = {'nodes': [
        {'node_hash': 'bb', 'payload': 'two'},
        {'node_hash': 'cc', 'payload': 'three'}
    ]}
    merged = merge_forests(a, b)
    # nodes should be deduplicated and sorted by node_hash
    hashes = [n['node_hash'] for n in merged['nodes']]
    assert hashes == ['aa', 'bb', 'cc']


def test_merge_conflict_reported():
    a = {'nodes': [
        {'node_hash': 'aa', 'payload': 'one'},
    ]}
    b = {'nodes': [
        {'node_hash': 'aa', 'payload': 'different'},
    ]}
    # without context, local preferred
    merged = merge_forests(a, b)
    assert 'conflicts' in merged
    assert merged['conflicts'][0]['node_hash'] == 'aa'
    assert merged['conflicts'][0]['winner'] == 'local'
    # with remote context carrying higher lamport, remote should win
    merged2 = merge_forests(a, b, remote_context={'lamport': 5})
    assert 'conflicts' in merged2
    assert merged2['conflicts'][0]['winner'] == 'remote'
    # ensure merged node payload is remote when remote wins
    hashes = [n['node_hash'] for n in merged2['nodes']]
    assert 'aa' in hashes
    node = [n for n in merged2['nodes'] if n['node_hash']=='aa'][0]
    assert node['payload'] == 'different'
