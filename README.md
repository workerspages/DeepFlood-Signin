
# 🌊 DeepFlood Auto Sign-in & AI Reply Bot

[![Docker Image](https://img.shields.io/badge/docker-ghcr.io-blue?logo=docker)](https://github.com/workerspages/deepflood-signin/pkgs/container/deepflood-signin)
[![Python](https://img.shields.io/badge/python-3.9+-yellow.svg?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**DeepFlood 论坛自动签到与 AI 智能回复助手**

这是一个基于 Python、Selenium 和 AI 大模型（OpenAI/New-API）开发的自动化工具，专为 DeepFlood 论坛设计。它不仅能帮助你每日自动签到领取奖励，还能通过 RSS 监控新帖，利用 AI 理解帖子内容并生成简短、自然、高质量的回复，从而保持账号活跃度。

---

## ✨ 核心特性

*   **✅ 全自动签到**
    *   每日定时自动访问论坛，点击签到并领取“试试手气”奖励。
    *   支持无头模式（Headless）运行，无需图形界面。

*   **🤖 上下文感知 AI 回复**
    *   **智能分析**：通过 RSS 获取新帖，利用 NLP 技术分析帖子情感（求助、讨论、分享）和内容。
    *   **拟人化生成**：集成 OpenAI 格式接口，生成 1-10 字的简短回复（如：“技术贴，收藏了 👍”、“试试看，加油”），拒绝机械式长篇灌水。
    *   **质量风控**：内置关键词过滤和重复检测，确保回复内容安全且不重复。

*   **🛡️ 强力浏览器仿真**
    *   使用 `undetected-chromedriver` 绕过 Cloudflare 等反爬虫检测。
    *   **Cookie 持久化**：自动保存和刷新浏览器 Cookie，避免频繁失效。
    *   **环境自适应**：自动适配 Docker 环境下的 Chrome 版本。

*   **⚙️ 极度灵活的配置 (New!)**
    *   **全环境变量支持**：所有配置项均可直接在 `docker-compose.yml` 中定义，无需修改代码或 JSON 文件。
    *   **多级配置优先级**：自动处理 Cookie 文件 > 环境变量 > 默认配置的优先级逻辑。

*   **📢 多渠道通知**
    *   任务完成后发送详细报告（签到结果、回复内容、统计数据）。
    *   支持 Telegram、微信（PushPlus/企业微信/微加）、钉钉、飞书、Bark 等 20+ 种推送方式。

---

## 🚀 快速部署 (Docker Compose) - 推荐

这是最简单、最稳定的运行方式，无需配置复杂的 Python 环境。

### 1. 创建项目目录
在你的服务器上创建一个文件夹：
```bash
mkdir deepflood-signin && cd deepflood-signin
```

### 2. 创建配置文件
新建 `docker-compose.yml` 文件，并复制以下内容。
**请务必修改 `FORUM_SESSION_COOKIE` 和 `AI_API_KEY`。**

```yaml
version: '3.8'

services:
  deepflood-signin:
    image: ghcr.io/workerspages/deepflood-signin:latest
    container_name: deepflood-signin
    restart: always
    volumes:
      - ./data:/app/data      # 数据库持久化
      - ./config:/app/config  # Cookie 持久化
      - ./logs:/app/logs      # 日志文件
    environment:
      # --- 🔑 核心凭证 (必填) ---
      - FORUM_SESSION_COOKIE=你的Cookie字符串
      - AI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxx

      # --- 🌐 论坛配置 ---
      - FORUM_BASE_URL=https://www.deepflood.com
      
      # --- 🧠 AI 配置 ---
      - AI_BASE_URL=https://api.openai.com/v1  # 或第三方转发地址
      - AI_MODEL=gpt-3.5-turbo

      # --- ⏰ 调度配置 ---
      - SCHEDULER_START_TIME=09:00  # 每天运行时间 (24小时制)
      - REPLY_ENABLED=true          # 开启自动回复

      # --- 💬 通知配置 (选填) ---
      # Telegram 示例
      - TG_BOT_TOKEN=
      - TG_USER_ID=
      # PushPlus 示例
      - PUSH_PLUS_TOKEN=

      # --- 🔧 高级配置 (可选) ---
      - IN_DOCKER=true
      # 强制指定Chrome版本，防止自动下载驱动不匹配
      - CHROME_VERSION=142 
```

### 3. 启动服务
```bash
docker-compose up -d
```

### 4. 查看日志
```bash
docker-compose logs -f
```
如果看到 `已将最新Cookie保存到 config/cookie.json` 和 `点击签到图标成功`，说明部署成功！

---

## 🍪 如何获取 Cookie (新手必读)

Cookie 是机器人登录论坛的唯一凭证，获取错误的 Cookie 会导致任务失败。

1.  在电脑浏览器（建议 Chrome 无痕模式）打开 [DeepFlood 论坛](https://www.deepflood.com)。
2.  **登录账号**。
3.  按下 `F12` 打开开发者工具，切换到 **Network (网络)** 标签页。
4.  刷新页面 (`F5`)。
5.  在请求列表中点击第一个请求（通常是 `www.deepflood.com` 或 `home`）。
6.  在右侧 **Request Headers (请求头)** 中找到 `Cookie`。
7.  复制 `Cookie:` 冒号后面的**所有内容**，填入 `FORUM_SESSION_COOKIE`。

> **⚠️ 重要提示**：如果需要更换账号或更新失效的 Cookie，请务必先执行 `rm config/cookie.json` 删除旧的缓存文件，然后重启容器。

---

## 📖 详细配置指南

得益于最新的配置管理器，你可以通过环境变量控制几乎所有行为。

### 基础设置
| 变量名 | 说明 | 默认值 |
| :--- | :--- | :--- |
| `FORUM_SESSION_COOKIE` | 论坛登录凭证 | (无) |
| `AI_API_KEY` | AI 接口密钥 | (无) |
| `AI_BASE_URL` | AI 接口地址 | `http://localhost:3000/v1` |
| `AI_MODEL` | 使用的模型 | `gpt-3.5-turbo` |

### 行为控制
| 变量名 | 说明 | 默认值 |
| :--- | :--- | :--- |
| `SCHEDULER_START_TIME` | 每日任务启动时间 | `09:00` |
| `REPLY_ENABLED` | 是否开启自动回复 | `true` |
| `REPLY_MAX_REPLIES_PER_DAY` | 每日最大回复数 | `20` |
| `REPLY_MAX_LENGTH` | 回复最大字数 | `10` |
| `SIGNIN_ENABLED` | 是否开启签到 | `true` |

### 过滤与风控
| 变量名 | 说明 | 默认值 |
| :--- | :--- | :--- |
| `FILTER_EXCLUDED_KEYWORDS` | 标题含此类词则跳过(逗号分隔) | `广告,推广,加群` |
| `FILTER_EXCLUDED_CATEGORIES` | 板块黑名单 | `广告,灌水` |

*(更多变量请参考 `config_manager.py` 源码)*

---

## 🛠️ 本地开发

如果你想修改代码或在本地 Python 环境运行：

1.  **克隆仓库**
    ```bash
    git clone https://github.com/workerspages/deepflood-signin.git
    cd deepflood-signin
    ```

2.  **安装依赖**
    ```bash
    pip install -r requirements.txt
    ```

3.  **运行**
    *   **单次测试模式**（立即执行一次）：
        ```bash
        python forum_reply_main.py --mode once
        ```
    *   **计划任务模式**（挂机等待）：
        ```bash
        python forum_reply_main.py --mode schedule
        ```

---

## 📁 项目结构

```text
.
├── config/                 # 配置文件挂载点
├── data/                   # SQLite 数据库 (记录已处理帖子)
├── logs/                   # 运行日志
├── forum_reply/            # 核心源码
│   ├── ai/                 # AI 内容分析与回复生成
│   ├── api/                # 论坛 API 封装与浏览器控制
│   ├── config/             # 配置管理器
│   ├── database/           # 数据库操作
│   └── scheduler/          # 任务调度与签到逻辑
├── Dockerfile              # 镜像构建文件
├── docker-compose.yml      # 容器编排文件
└── notify.py               # 推送通知模块
```

---

## ⚠️ 免责声明

1.  本项目仅供 Python 编程学习和技术研究使用。
2.  请勿将本项目用于发布垃圾信息、广告或进行恶意刷屏。
3.  使用本项目所产生的任何后果（包括但不限于账号被封禁）由使用者自行承担。
4.  请合理设置回复频率（建议每日不超过 20 条），维护良好的社区环境。

---

## 🤝 贡献与支持

欢迎提交 Issue 反馈 Bug 或提交 Pull Request 改进代码。
如果是 Docker 运行问题，请先检查 Logs：`docker-compose logs -f --tail 100`。

**License**: MIT
