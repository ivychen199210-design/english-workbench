#!/bin/bash
# English Workbench 启动脚本
cd "$(dirname "$0")"
echo "🚀 启动 English Workbench..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
python3 -m uvicorn app:app --host 0.0.0.0 --port 8000
