# DeepFlood-Signin - 论坛自动签到与 AI 回帖机器人

![GitHub License](https://img.shields.io/github/license/workerspages/DeepFlood-Signin)
![Docker Pulls](https://img.shields.io/docker/pulls/workerspages/deepflood-signin)
![GitHub Stars](https://img.shields.io/github/stars/workerspages/DeepFlood-Signin?style=social)

一款专为 [DeepFlood 论坛](https://www.deepflood.com) 设计的自动化工具，集成了 **每日自动签到** 和 **AI 智能回帖** 两大核心功能。项目通过模拟真实浏览器行为，确保稳定运行，并利用 AI 模型分析帖子内容，生成简短、自然、人性化的回复。

整个项目被封装在 Docker 中，实现了“一次配置，永久运行”的终极目标。

## ✨ 核心功能

*   **🏆 自动每日签到**: 每日定时启动，模拟真人操作，完成签到任务，不错过任何奖励。
*   **🧠 AI 智能回帖**:
    *   实时从 RSS 源获取最新帖子。
    *   调用 AI 模型（兼容 OpenAI, new-api, one-api, 智谱等）分析帖子内容。
    *   自动生成**简短（1-10字）、自然、高质量**的回复。
    *   内置模板库，在 AI 失效时自动降级，确保回复不中断。
*   **🛡️ 强大的反-反爬虫能力**:
    *   使用 `undetected-chromedriver` 模拟真实浏览器环境，有效对抗 Cloudflare 的 WAF 防火墙和人机验证。
    *   所有关键操作（签到、获取帖子、回帖）均在完整的浏览器环境中执行，成功率极高。
*   **🔑 Cookie 自动续期与持久化 (Set it and Forget it!)**:
    *   **告别手动更换 Cookie**！首次配置成功后，程序会在每次运行时自动从浏览器获取最新的 `cf_clearance` 和 `session` 令牌。
    *   最新的 Cookie 会被自动加密保存在 `./config/cookie.json` 文件中，并被优先加载。
    *   实现了真正的“一次配置，永久有效”，只要您不主动登出或修改密码。
*   **🚀 Docker 一键部署**: 提供 `docker-compose.yml`，只需修改少量配置即可一键启动，无需关心复杂的环境依赖。
*   **🔔 丰富的任务通知**: 支持通过 **Telegram**、企业微信、钉钉等多种渠道发送每日任务报告，让你对运行状态了如指掌。

---

## 🚀 快速开始 (Docker 部署)

推荐使用 Docker Compose 进行部署，这是最简单、最稳定的方式。

### 准备工作

*   一台安装了 `Git` 的服务器或电脑。
*   已安装 `Docker` 和 `Docker Compose`。

### 部署步骤

#### 1. 克隆项目

```bash
git clone https://github.com/workerspages/DeepFlood-Signin.git
cd DeepFlood-Signin
```

#### 2. 创建必要的目录和文件

这是**非常重要**的一步，可以防止因目录不存在而导致的启动失败。

```bash
# 创建用于持久化数据的目录
mkdir -p data config

# 创建一个空的配置文件，程序需要它存在
touch config/forum_config.json
```

#### 3. 配置 `docker-compose.yml`

这是您**唯一**需要修改的文件。请用您喜欢的编辑器打开 `docker-compose.yml`，并根据其中的注释修改配置。

```yaml
services:
  deepflood-signin:
    # 使用 ghcr.io 上预构建的官方镜像
    image: ghcr.io/workerspages/deepflood-signin:latest
    container_name: deepflood-signin
    environment:
      # ==================================================
      # 核心配置 (请务必修改)
      # ==================================================
      
      # 论坛配置
      - FORUM_SESSION_COOKIE=your_session_cookie_here
      - FORUM_BASE_URL=https://www.deepflood.com
      
      # AI 配置
      - AI_API_KEY=your_ai_api_key_here
      - AI_BASE_URL=your_ai_base_url_here
      - AI_MODEL=your_ai_model_here
      
      # ==================================================
      # 调度器与功能开关
      # ==================================================
      
      # 任务开始时间 (HH:MM 格式)
      - SCHEDULER_START_TIME=09:00
      # 全局回复开关 (true 或 false)
      - REPLY_ENABLED=true
      
      # ==================================================
      # 通知服务配置 (可选)
      # ==================================================
      
      # Telegram 机器人 Token
      - TG_BOT_TOKEN=
      # Telegram 用户的 User ID
      - TG_USER_ID=
      
      # ==================================================
      # 环境配置 (一般无需修改)
      # ==================================================
      
      # 标记在 Docker 容器中运行
      - IN_DOKCER=true
      # 为本地运行环境指定Chrome主版本号，在Docker中请留空
      - CHROME_VERSION=
      
    volumes:
      # 将 data 目录挂载到主机，用于持久化数据库
      - ./data:/app/data
      # 将 config 目录挂载到主机，方便修改配置
      - ./config:/app/config
      
    restart: always

```

#### 4. 构建并启动容器

在 `docker-compose.yml` 文件所在的目录，运行以下命令：

```bash
# --build 参数会强制使用最新的代码构建镜像
# --force-recreate 确保旧的容器被替换
docker-compose up -d --build --force-recreate
```

#### 5. 检查运行日志

等待一两分钟，然后运行以下命令查看日志，确保一切正常：

```bash
docker-compose logs -f
```

如果您看到“**每日签到成功完成，并已刷新Cookie**”和“**已将最新Cookie保存到 config/cookie.json**”等日志，那么恭喜您，部署成功！

---

## 🔧 配置指南

### 如何获取完整的 Cookie

这是**首次配置最关键**的一步。由于网站有 Cloudflare 保护，我们必须获取包含 `cf_clearance` 令牌的完整 Cookie。

1.  在您的电脑浏览器上，打开 DeepFlood 论坛并**登录**。
2.  按 `F12` 键打开“开发者工具”，切换到 **“网络” (Network)** 选项卡。
3.  刷新一下页面。
4.  在网络请求列表中，找到任意一个向 `www.deepflood.com` 发出的请求，点击它。
5.  在右侧出现的窗口中，找到 **“标头” (Headers)** -> **“请求标头” (Request Headers)**。
6.  向下滚动，找到名为 `cookie` 的一行。
7.  **右键点击 `cookie` 这一整行的值**，选择 **“复制值” (Copy value)**。
8.  将复制的**完整字符串**粘贴到 `docker-compose.yml` 的 `FORUM_SESSION_COOKIE` 字段中。

### 环境变量详解

| 变量名                  | 是否必须 | 描述                                                                                                        | 示例                                               |
| ----------------------- | -------- | ----------------------------------------------------------------------------------------------------------- | -------------------------------------------------- |
| `FORUM_SESSION_COOKIE`  | **是**   | 首次运行时使用的完整 Cookie 字符串。                                                                        | `"cf_clearance=...; session=...; ..."`             |
| `AI_API_KEY`            | **是**   | 您的 AI 服务 API Key。                                                                                      | `"sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxx"`                |
| `AI_BASE_URL`           | **是**   | 您的 AI 服务 API 地址。                                                                                     | `"https://api.openai.com/v1"`                      |
| `AI_MODEL`              | **是**   | 您要使用的 AI 模型名称。                                                                                    | `"gpt-3.5-turbo"`                                  |
| `SCHEDULER_START_TIME`  | 否       | 每日任务的启动时间，使用 24 小时制 `HH:MM` 格式。                                                           | `"09:30"`                                          |
| `REPLY_ENABLED`         | 否       | 是否开启 AI 回帖功能。`true` 或 `false`。                                                                   | `true`                                             |
| `TG_BOT_TOKEN`          | 否       | Telegram Bot 的 Token，用于发送通知。                                                                       | `"123456:ABC-DEF123456..."`                        |
| `TG_USER_ID`            | 否       | 您的 Telegram User ID，用于接收通知。                                                                       | `"123456789"`                                      |
| `CHROME_VERSION`        | **是**   | **请勿修改！** 这是为 Docker 环境固定的 Chrome 版本号，用于避免网络错误。                                   | `"142"`                                            |

---

## ⚙️ 详细配置说明

除了环境变量，您还可以通过 `config/forum_config.json` 进行更细致的配置（Docker 映射到 `/app/config/forum_config.json`）：

| 配置项 | 说明 | 默认值 |
| :--- | :--- | :--- |
| **scheduler.start_time** | 每日任务启动时间 (HH:MM) | "09:00" |
| **scheduler.runs_per_day** | 每天唤醒检查次数 | 20 |
| **reply.max_replies_per_day** | 每天最大回复帖子数 | 20 |
| **reply.max_length** | AI 回复最大字数 | 10 |
| **reply.reply_probability** | 回复概率 (0-1) | 0.8 |
| **filter.excluded_keywords** | 标题/内容含此关键词则跳过 | ["广告", "推广", "加群"] |
| **ai.provider** | AI 提供商标识 | "new-api" |

### 通知服务

本项目集成 `notify.py`，支持极其丰富的推送渠道。只需在环境变量中设置对应的 Key 即可启用。
常用变量示例：
*   **Telegram**: `TG_BOT_TOKEN`, `TG_USER_ID`
*   **PushPlus**: `PUSH_PLUS_TOKEN`
*   **Server酱**: `PUSH_KEY`
*   **钉钉**: `DD_BOT_TOKEN`, `DD_BOT_SECRET`
*   **企业微信**: `QYWX_KEY` (机器人)

*(更多支持请参考源码中的 `notify.py`)*



## 📈 日志与维护

*   **实时查看日志**:
    ```bash
    docker-compose logs -f
    ```
*   **停止服务**:
    ```bash
    docker-compose down
    ```
*   **更新项目**:
    ```bash
    # 1. 拉取最新的代码
    git pull
    
    # 2. 重新构建并启动
    docker-compose up -d --build --force-recreate
    ```

## ❓ 常见问题 (FAQ)

1.  **启动时报错 `SSLZeroReturnError` 或 `TLS/SSL connection has been closed`?**
    *   **原因**: `CHROME_VERSION` 环境变量丢失或为空。
    *   **解决**: 确保您的 `docker-compose.yml` 中包含 `- CHROME_VERSION="142"` 这一行。

2.  **日志显示“无法获取帖子”或 Cookie 失效？**
    *   **原因**: 您的初始 `FORUM_SESSION_COOKIE` 不完整或已过期。
    *   **解决**: 严格按照【如何获取完整的 Cookie】部分的教程，从**网络 (Network)** 面板重新复制最新的、完整的 Cookie 字符串，然后更新 `docker-compose.yml` 并重启服务。

3.  **启动时报错 `config/forum_config.json: no such file or directory`?**
    *   **原因**: 您在启动前没有创建必要的目录和文件。
    *   **解决**: 运行 `mkdir -p config data` 和 `touch config/forum_config.json` 来创建它们。

## 🤝 贡献

欢迎提交 Pull Requests 或 Issues 来帮助改进这个项目。

## 📄 许可证

本项目使用 [MIT License](LICENSE)。

## 🧑‍💻 作者

*   **原始项目**: [zpaeng/DeepFlood-Signin](https://github.com/zpaeng/DeepFlood-Signin)
*   **功能增强与调试**: 由 AI 助手与您共同完成

希望这份文档能帮助您顺利使用！
