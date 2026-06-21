#!/bin/bash
# DeepSeek Token Monitor 启动脚本
# Usage:
#   ./run.sh            # 使用环境变量中的 DEEPSEEK_API_KEY
#   DEEPSEEK_API_KEY=sk-xxx ./run.sh   # 直接指定 key

cd "$(dirname "$0")"

if [ -z "$DEEPSEEK_API_KEY" ]; then
    echo "⚠️  未设置 DEEPSEEK_API_KEY 环境变量"
    echo "请通过以下方式设置："
    echo "  export DEEPSEEK_API_KEY=sk-xxx"
    echo "  DEEPSEEK_API_KEY=sk-xxx ./run.sh"
    echo ""
    echo "程序将以「无 Key」模式启动，只能看到提示信息。"
fi

echo "启动 DeepSeek Token Monitor..."
python3 app.py
