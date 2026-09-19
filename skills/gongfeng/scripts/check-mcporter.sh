#!/usr/bin/env bash
# check-mcporter.sh - 检查 mcporter 是否已配置 gongfeng 服务
# Usage: bash skill/scripts/check-mcporter.sh
# 接入方式详见 skill/SKILL.md
# 一律通过 npx 调用 mcporter，无需全局安装 mcporter

set -e

echo "🔍 检查 npx / mcporter 是否可用..."

if ! command -v npx &>/dev/null; then
  echo "❌ 未找到 npx。请先安装 Node.js 20 或更高版本（安装后自带 npm / npx），再重新运行本脚本。"
  echo "   可参考：https://nodejs.org/ ，或使用 nvm、fnm 等版本管理器。"
  exit 1
fi

echo "✅ 将使用 npx 运行 mcporter"
echo ""
echo "🔍 列出已配置的 MCP 服务..."
npx mcporter list 2>&1

echo ""
echo "🔍 检查 gongfeng 服务..."
if npx mcporter list 2>&1 | grep -q "gongfeng"; then
  echo "✅ gongfeng 服务已配置"
else
  echo "⚠️  gongfeng 服务未在 mcporter 中配置"
  echo ""
  echo "请在 mcporter 配置文件中添加（接入方式详见 skill/SKILL.md）："
  cat <<'EOF'
{
  "mcpServers": {
    "gongfeng": {
      "url": "https://mcpgw.knot.woa.com/gongfeng",
      "headers": {
        "Authorization": "Bearer tai_pat_xxx"
      }
    }
  }
}
EOF
  exit 1
fi
