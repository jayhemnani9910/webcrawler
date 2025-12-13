#!/bin/bash
# Ensure secure permissions for keys and DB
find keys/ -type f -exec chmod 600 {} \;
chmod 700 keys
chmod 600 watcher.db config/*.key 2>/dev/null || true
