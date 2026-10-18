#!/usr/bin/env bash
set -euo pipefail
REPO_URL="${REPO_URL:-https://github.com/lssopk/visual-novel-vault.git}"
DEST="${DEST:-$HOME/visual-novel-vault}"
if ! command -v git >/dev/null; then echo '需要先安装 git'; exit 1;fi
if [[ -d "$DEST/.git" ]]; then
  echo "已有项目：$DEST，尝试更新"
  git -C "$DEST" pull --ff-only
elif [[ -e "$DEST" ]]; then
  echo "目标目录已存在且不是 Git 仓库：$DEST";exit 1
else
  git clone "$REPO_URL" "$DEST"
fi
cd "$DEST" && ./deploy.sh
