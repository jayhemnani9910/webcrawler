#!/bin/bash
# Ensure secure permissions for keys and DB.
# This used to end in `|| true`, so it reported success no matter how many chmod
# calls failed, and it had no set -e either.
set -euo pipefail

fail=0
if [ -d keys ]; then
  find keys/ -type f -exec chmod 600 {} \; || fail=1
  chmod 700 keys || fail=1
else
  echo "keys/ not found; nothing to secure there" >&2
fi

if [ -f watcher.db ]; then
  chmod 600 watcher.db || fail=1
fi

# config/*.key was in the original list but no config/ directory exists in this
# repo. Guarded so an absent directory is not an error, and a real failure is.
if compgen -G "config/*.key" > /dev/null; then
  chmod 600 config/*.key || fail=1
fi

if [ "$fail" -ne 0 ]; then
  echo "one or more chmod operations failed" >&2
  exit 1
fi
echo "permissions secured"
