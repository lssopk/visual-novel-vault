#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v docker >/dev/null 2>&1; then
  echo '错误：请先安装 Docker Engine 和 Docker Compose 插件' >&2
  exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
  echo '错误：缺少 docker compose 插件' >&2
  exit 1
fi

printf '\n=== 幕间 · 个人视觉小说调查档案馆（公网 6099）===\n'
printf '默认监听 0.0.0.0:6099；可在 .env 中设置 BIND_ADDR=127.0.0.1 改为仅本机访问。\n'
printf '安全提醒：公网明文 HTTP 不能保护管理密码及 API Token，请尽快使用 HTTPS 反代。\n\n'

# 先构建镜像并在未公开端口时初始化管理员账户。
docker compose build

has_admin() {
  docker compose run --rm --no-deps -T app python -c "from db import init,connect; init(); db=connect(); raise SystemExit(0 if db.execute(\"SELECT 1 FROM settings WHERE key='admin_password'\").fetchone() else 1)" >/dev/null 2>&1
}
if ! has_admin; then
  if [[ ! -t 0 ]]; then
    echo '首次运行需要交互式终端设置管理员密码（不少于 12 位）。' >&2
    echo '请在 SSH 终端直接执行 ./deploy.sh。' >&2
    exit 1
  fi
  printf '首次安装：设置管理员密码（至少 12 位）：\n'
  read -r -s -p '管理员密码: ' ADMIN_PASS; printf '\n'
  if [[ ${#ADMIN_PASS} -lt 12 ]]; then
    echo '密码不足 12 位，未开放端口。' >&2
    exit 1
  fi
  printf '%s\n' "$ADMIN_PASS" | docker compose run --rm --no-deps -T app python manage.py init-admin --password-stdin
  unset ADMIN_PASS
fi

docker compose up -d --no-build

# 检查 HTTP 服务是否准备就绪。
healthy=0
for ((i=1; i<=20; i++)); do
  if command -v curl >/dev/null 2>&1; then
    if curl -fsS --max-time 2 http://127.0.0.1:6099/api/v1/health >/dev/null 2>&1; then healthy=1; break; fi
  else
    if docker compose exec -T app python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:6099/api/v1/health',timeout=2)" >/dev/null 2>&1; then healthy=1; break; fi
  fi
  sleep 2
done
if [[ $healthy -ne 1 ]]; then
  echo '网站未通过健康检查，请运行 docker compose logs --tail=100 app 排查。' >&2
  exit 1
fi

# 只在用户明确选择公网绑定时开启已启用的系统防火墙端口。
if [[ "${BIND_ADDR:-0.0.0.0}" == "0.0.0.0" ]]; then
  if command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -qi '^Status: active'; then
    if ufw allow 6099/tcp; then
      echo '已在 UFW 中允许 TCP 6099。'
    else
      echo '警告：UFW 开放失败，需要手动放行 TCP 6099。' >&2
    fi
  elif command -v firewall-cmd >/dev/null 2>&1 && firewall-cmd --state 2>/dev/null | grep -qx running; then
    if firewall-cmd --permanent --add-port=6099/tcp && firewall-cmd --reload; then
      echo '已在 firewalld 中允许 TCP 6099。'
    else
      echo '警告：firewalld 开放失败，需要手动放行 TCP 6099。' >&2
    fi
  fi
fi

printf '\n部署成功！本机检测：http://127.0.0.1:6099/api/v1/health\n'
if [[ "${BIND_ADDR:-0.0.0.0}" == "0.0.0.0" ]]; then
  printf '公网访问：http://<VPS公网IPv4>:6099\n'
  printf '如果外网仍无法访问，检查云服务商安全组、防火墙（TCP 6099）或 VPS 的自定义 nftables/iptables 规则。\n'
fi
printf 'Codex 密钥：docker compose exec app python manage.py create-key --name codex\n'
printf '启用 HTTPS 反代后：在 .env 中设置 PUBLIC_HTTPS=1 并重新运行 ./deploy.sh。\n'
