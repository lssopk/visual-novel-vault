#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if ! command -v docker >/dev/null; then echo '请先安装 Docker Engine 和 Docker Compose 插件';exit 1;fi
if ! docker compose version >/dev/null 2>&1; then echo '缺少 docker compose 插件';exit 1;fi
printf '\n=== 幕间 · 个人视觉小说调查档案馆 ===\n'
docker compose up -d --build
printf '\n已启动：http://127.0.0.1:6099\n'
if [[ -t 0 ]]; then
  printf '首次部署请设置管理员密码（至少12位）。如果已有密码，直接回车跳过：\n'
  read -r -s -p '管理员密码: ' ADMIN_PASS; echo
  if [[ -n "$ADMIN_PASS" ]]; then
    printf '%s\n' "$ADMIN_PASS" | docker compose exec -T app python manage.py init-admin --password-stdin
  fi
  unset ADMIN_PASS
else
  echo '非交互环境：请运行 docker compose exec app python manage.py init-admin 初始化管理密码。'
fi
printf '\n检查服务：curl http://127.0.0.1:6099/api/v1/health\n'
printf 'Codex 密钥：docker compose exec app python manage.py create-key --name codex\n'
printf '启用 HTTPS 反代后：在 .env 中设置 PUBLIC_HTTPS=1，再运行 ./deploy.sh\n'
