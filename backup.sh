#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p backups
OUT="backups/vault-$(date +%Y%m%d-%H%M%S).sqlite3"
# SQLite 在线备份写入容器 /tmp，再通过 docker cp 导出到宿主机
TMP="/tmp/vault-backup-$$.sqlite3"
docker compose exec -T app python -c "import sqlite3; src=sqlite3.connect('/data/vault.sqlite3'); dst=sqlite3.connect('$TMP'); src.backup(dst); dst.close(); src.close()"
docker cp "visual-novel-vault:$TMP" "$OUT"
docker compose exec -T app rm -f "$TMP"
chmod 600 "$OUT"
echo "备份已保存：$OUT"
