#!/usr/bin/env bash
set -Eeuo pipefail
BASE="$(cd "$(dirname "$0")" && pwd -P)"
MAGIC='DELETE-VISUAL-NOVEL'
[[ "${1:-}" == '--purge' ]] || { echo '用法：bash ./uninstall.sh --purge [--yes]';exit 2; }
[[ -f "$BASE/compose.yaml" && -f "$BASE/server.py" && -f "$BASE/db.py" ]] || { echo '项目路径不正确，拒绝清理';exit 1; }
[[ "$BASE" != / && "$BASE" != /root && "$BASE" != /home && "$BASE" != /mnt/data ]] || { echo '危险路径，拒绝清理';exit 1; }
printf '\n将彻底卸载个人视觉小说调查档案馆：%s\n' "$BASE"
echo '这将永久删除网站的独立容器、镜像、SQLite 数据卷（全部游戏、笔记、AI 密钥）及此目录中的文件。'
echo '不会删除其他 Docker 项目、共享 Docker Engine、GitHub 仓库或外部备份。'
if [[ "${2:-}" != '--yes' ]]; then
  read -r -p "确认卸载请输入 ${MAGIC}: " ANSWER </dev/tty
  [[ "$ANSWER" == "$MAGIC" ]] || { echo '已取消';exit 1; }
fi
cd "$BASE"
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  docker compose down --volumes --rmi all --remove-orphans
else
  echo 'Docker 不可用，拒绝删除目录以免遗留资源。' >&2;exit 1
fi
cd /
rm -rf -- "$BASE"
echo '卸载完成。请自行移除不再使用的反向代理配置与防火墙 TCP 6099 规则。'
