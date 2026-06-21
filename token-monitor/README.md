# DeepSeek Token Monitor

macOS 菜单栏小工具，实时监控 DeepSeek API 余额和消费情况。

## 安装

```bash
cd ~/token-monitor
pip3 install -r requirements.txt
```

如果 pyobjc 编译失败（新版本 macOS/Xcode），使用：

```bash
CFLAGS="-Wno-error=default-const-init-var-unsafe" pip3 install -r requirements.txt
```

## 使用

```bash
export DEEPSEEK_API_KEY=sk-xxx
cd ~/token-monitor
python3 app.py
```

或直接用启动脚本：

```bash
DEEPSEEK_API_KEY=sk-xxx ~/token-monitor/run.sh
```

## 功能

- **菜单栏余额显示**：实时显示 DeepSeek 账户余额
- **今日消费**：对比余额变化推算当日消费金额
- **本月消费**：汇总本月累计消费
- **自动刷新**：每 5/15/30 分钟自动查询，可暂停
- **一键复制**：点击余额菜单项复制到剪贴板
- **历史记录**：SQLite 本地存储，支持清除

## 目录结构

```
token-monitor/
├── app.py              # 主程序 (rumps 菜单栏)
├── deepseek_api.py     # DeepSeek API 封装
├── storage.py          # SQLite 数据存储
├── config.py           # 配置管理
├── run.sh              # 启动脚本
└── requirements.txt    # Python 依赖
```

## 数据存储

历史数据存储在 `~/.token-monitor/usage.db` (SQLite)，配置在 `~/.token-monitor/config.json`。
