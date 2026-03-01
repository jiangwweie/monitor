#!/usr/bin/env bash
# 自动推送脚本 – 使用环境变量 GITHUB_TOKEN（Personal Access Token）
# 请先在本机或 CI 环境中导出 GITHUB_TOKEN，确保它拥有 repo 权限。
# 示例： export GITHUB_TOKEN=ghp_YourTokenHere

set -e

# 检查是否已设置 token
if [[ -z "$GITHUB_TOKEN" ]]; then
  echo "错误: 未设置 GITHUB_TOKEN 环境变量。请先导出你的 Personal Access Token。"
  exit 1
fi

# 配置远程 URL（使用 token）
REPO_URL="https://$GITHUB_TOKEN@github.com/$(git config --get remote.origin.url | sed -e 's|https://||' -e 's|git@||' -e 's|:|/|')"

git remote set-url origin "$REPO_URL"

git push origin $(git rev-parse --abbrev-ref HEAD)

# 可选：恢复为原始 HTTPS URL（不含 token）
# git remote set-url origin "https://github.com/$(git config --get remote.origin.url | sed -e 's|https://||')"
