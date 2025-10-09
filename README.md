# DeepFlood 论坛自动签到与回复工具

这是一个专为 [DeepFlood 论坛](https://www.deepflood.com/) 设计的自动化工具，能够实现以下核心功能：

- **自动签到**：每日自动执行论坛签到，获取积分。
- **智能回复**：
    - 监控论坛最新帖子。
    - 使用 AI（支持多种模型，如 GPT、Gemini 等）生成人性化的简短回复。
    - 自动发布回复，模拟真实用户操作，有效规避检测。
- **高度可配置**：几乎所有参数均可通过配置文件或环境变量进行调整，例如回复频率、AI 模型、代理设置等。
- **多渠道通知**：支持通过 Telegram、钉钉等多种方式发送任务报告，让您随时了解运行状态。
- **多种部署方式**：支持 Docker、GitHub Actions 以及直接在本地/服务器运行。

## 快速开始 (Docker 推荐)

我们强烈推荐使用 **Docker** 来部署此项目，这是最简单、最稳定的方式。

### 1. 准备工作

- **安装 Docker 和 Docker Compose**：请确保您的系统中已安装这两个工具。
- **下载项目**：
  ```bash
  git clone https://github.com/zpaeng/DeepFlood-Signin.git
  cd DeepFlood-Signin
  ```

### 2. 配置文件

项目包含两个主要的配置文件：

- `.env`：用于存放**密钥和个人身份信息**，例如论坛 Cookie 和 AI 的 API Key。
- `config/forum_config.json`：用于配置**程序的行为**，例如启用哪些功能、回复频率、AI 模型名称等。

**首次运行时，您需要手动创建这两个文件：**

1.  **创建 `.env` 文件**：
    复制 `.env.example` 文件来创建您的 `.env` 文件。
    ```bash
    cp .env.example .env
    ```
    然后，编辑 `.env` 文件，填入您的个人信息：
    - `FORUM_SESSION_COOKIE`：**（必需）** 您的 DeepFlood 论坛 `session` cookie。
    - `AI_API_KEY`：**（必需）** 您的 AI 服务 API Key。
    - `AI_BASE_URL`：**（必需）** 您的 AI 服务 API 地址。
    - `TG_BOT_TOKEN` / `TG_USER_ID`：如果您需要 Telegram 通知，请填写。

2.  **创建 `forum_config.json` 文件**：
    您可以复制示例文件 `config/forum_config.json.example` 来创建它。
    ```bash
    cp config/forum_config.json.example config/forum_config.json
    ```
    或者，您也可以在**本地环境**（非 Docker）下运行以下命令，程序会自动生成一份默认配置：
    ```bash
    python forum_reply_main.py --init-config
    ```

    **重要配置项说明** (`config/forum_config.json`):
    - `scheduler.run_mode`: 运行模式，`"schedule"` 为每日定时运行，`"once"` 为仅运行一次。**Docker 部署时应保持为 `"schedule"`**。
    - `scheduler.start_time`: 当 `run_mode` 为 `"schedule"` 时，每日的启动时间（24小时制，例如 `"09:30"`）。
    - `reply.enabled`: 是否启用自动回复功能。`true` 为开启，`false` 为关闭。
    - `reply.daily_reply_limit`: 每日最大回复数量，防止滥用。

### 3. 启动服务 (Docker)

完成配置后，在项目根目录运行以下命令即可启动服务：

```bash
docker-compose up --build -d
```

- `--build`：首次启动或代码更新后需要此参数，用于构建镜像。
- `-d`：让容器在后台运行。

服务启动后，它将根据您在 `forum_config.json` 中设置的时间自动执行任务。

### 4. 查看日志

您可以随时查看程序的运行日志来确认其状态：

```bash
docker-compose logs -f
```

## 本地运行 (备用)

如果您不想使用 Docker，也可以直接在本地环境运行。

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置

同 Docker 部署方式，请先配置好 `.env` 和 `config/forum_config.json` 文件。

### 3. 运行

根据您的需求，选择以下一种模式运行：

- **定时调度模式**：
  程序将根据配置文件中的 `start_time` 每天自动运行。
  ```bash
  python forum_reply_main.py --mode schedule
  ```

- **单次运行模式**：
  程序将立即执行一次签到和回复任务，然后退出。
  ```bash
  python forum_reply_main.py --mode once
  ```

## 命令行参数说明

您可以通过命令行参数覆盖配置文件的部分设置。

- `--config <path>`：指定配置文件的路径。默认为 `config/forum_config.json`。
  ```bash
  python forum_reply_main.py --config my_custom_config.json
  ```

- `--mode <once|schedule>`：指定运行模式。
  - `once`：运行一次后立即退出。
  - `schedule`：根据配置文件中的时间定时运行。
  此参数会覆盖配置文件中的 `run_mode` 设置。

- `--init-config`：初始化配置文件。如果 `config/forum_config.json` 不存在，此命令会创建一份默认的配置文件。


## 开源协议

本项目采用 [MIT License](LICENSE) 开源。

## 免责声明

- 本工具仅供学习和技术研究使用，请勿用于非法用途。
- 用户在使用本工具前，请仔细阅读并同意遵守目标网站的使用协议和相关规定。
- 因使用本工具而导致的任何意外、疏忽、合约毁坏、诽谤、版权或知识产权侵犯及其所造成的各种损失，作者概不负责，亦不承担任何法律责任。
- 任何单位或个人认为本项目可能涉嫌侵犯其合法权益，应及时反馈，作者将在收到通知后尽快处理。


## 致谢

本项目的部分代码实现参考了 [yowiv/NodeSeek-Signin](https://github.com/yowiv/NodeSeek-Signin) 项目，特此感谢。
