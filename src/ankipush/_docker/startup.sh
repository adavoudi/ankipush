#!/bin/bash
set -e

mkdir -p /data/addons21
rm -rf /data/addons21/ankipush_addon
cp -r /app/addon /data/addons21/ankipush_addon

echo "[i] Launching Anki..."
anki -b /data
exit $?
