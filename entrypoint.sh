#!/bin/bash
set -e

# Fix /data ownership for bind mounts created by Docker as root
mkdir -p /data
chown -R appuser:appuser /data

gosu appuser alembic upgrade head

exec gosu appuser "$@"
