"""
配置管理模块
支持从JSON文件和环境变量加载配置
"""

import os
import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict, field
from pathlib import Path
from dotenv import load_dotenv


@dataclass
class ForumConfig:
    """论坛API配置"""
    base_url: str = "https://www.deepflood.com"
    session_cookie: str = ""
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    request_timeout: int = 30
    max_retries: int = 3
    rate_limit_per_minute: int = 20
    enable_proxy: bool = False
    proxy_url: str = ""
    # 定义持久化 Cookie 文件的路径
    cookie_file_path: str = "config/cookie.json"


@dataclass
class AIConfig:
    """AI配置 - 适配new-api项目"""
    provider: str = "new-api"
    model: str = "gpt-3.5-turbo"
    api_key: str = ""
    base_url: str = "http://localhost:3000/v1"
    max_tokens: int = 30
    temperature: float = 0.8


@dataclass
class ReplyConfig:
    """回复配置 - 短回复特化"""
    enabled: bool = True
    reply_probability: float = 0.8
    min_delay_seconds: int = 60
    max_delay_seconds: int = 300
    max_replies_per_hour: int = 10
    max_replies_per_day: int = 20
    max_length: int = 10
    min_length: int = 1
    enable_emoji: bool = True
    template_fallback: bool = True


@dataclass
class FilterConfig:
    """过滤配置"""
    min_post_age_minutes: int = 5
    max_post_age_hours: int = 24
    excluded_keywords: List[str] = field(default_factory=lambda: ["广告", "推广", "加群", "微信"])
    required_keywords: List[str] = field(default_factory=list)
    min_content_length: int = 10
    max_content_length: int = 5000
    excluded_categories: List[str] = field(default_factory=lambda: ["广告", "灌水"])


@dataclass
class DatabaseConfig:
    """数据库配置"""
    path: str = "data/forum_reply.db"
    backup_enabled: bool = True
    backup_interval_hours: int = 24


@dataclass
class LoggingConfig:
    """日志配置"""
    level: str = "INFO"
    file_path: str = "logs/forum_reply.log"
    max_file_size: str = "10MB"
    backup_count: int = 5


@dataclass
class SchedulerConfig:
    """调度器配置"""
    run_mode: str = "schedule"
    start_time: str = "09:00"
    runs_per_day: int = 20
    time_between_runs_minutes_min: int = 30
    time_between_runs_minutes_max: int = 60
    min_post_interval_seconds: int = 10
    max_post_interval_seconds: int = 30


@dataclass
class SignInConfig:
    """签到配置"""
    enabled: bool = True
    random_bonus: bool = False
    headless: bool = True


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_file: str = "config/forum_config.json"):
        self.config_file = config_file
        self.forum_config = ForumConfig()
        self.ai_config = AIConfig()
        self.reply_config = ReplyConfig()
        self.filter_config = FilterConfig()
        self.database_config = DatabaseConfig()
        self.logging_config = LoggingConfig()
        self.scheduler_config = SchedulerConfig()
        self.signin_config = SignInConfig()
        
        self.load_config()
    
    def load_config(self):
        """
        加载配置，并建立优先级:
        1. 持久化的 cookie.json 文件 (最高, 仅针对Cookie)
        2. 环境变量 (docker-compose.yml)
        3. forum_config.json 文件 (最低)
        """
        load_dotenv()
        try:
            # 1. 从 forum_config.json 加载基础配置
            if os.path.exists(self.config_file):
                self._load_from_file()
                print(f"配置从文件加载成功: {self.config_file}")
            else:
                print(f"配置文件不存在: {self.config_file}，使用默认配置")
            
            # 2. 从环境变量覆盖
            self._load_from_env()
            
            # 3. 尝试从持久化文件加载最新Cookie (最高优先级)
            self._load_cookie_from_file()
            
            # 4. 验证最终配置
            self._validate_config()
            
        except Exception as e:
            print(f"加载配置失败: {e}")
            raise
            
    def _load_cookie_from_file(self):
        """从持久化的 cookie.json 文件加载 Cookie"""
        cookie_file = self.forum_config.cookie_file_path
        try:
            if os.path.exists(cookie_file):
                with open(cookie_file, 'r', encoding='utf-8') as f:
                    cookie_data = json.load(f)
                    persistent_cookie = cookie_data.get("cookie_string")
                    if persistent_cookie:
                        self.forum_config.session_cookie = persistent_cookie
                        print(f"成功从持久化文件 {cookie_file} 加载最新Cookie。")
        except (FileNotFoundError, json.JSONDecodeError, Exception) as e:
            print(f"从 {cookie_file} 加载Cookie失败 (可能是首次运行)，将使用环境变量中的Cookie: {e}")

    def _load_from_file(self):
        """从JSON文件加载配置"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            if 'api' in config_data: self._update_dataclass(self.forum_config, config_data['api'])
            if 'ai' in config_data: self._update_dataclass(self.ai_config, config_data['ai'])
            if 'reply' in config_data: self._update_dataclass(self.reply_config, config_data['reply'])
            if 'filter' in config_data: self._update_dataclass(self.filter_config, config_data['filter'])
            if 'database' in config_data: self._update_dataclass(self.database_config, config_data['database'])
            if 'logging' in config_data: self._update_dataclass(self.logging_config, config_data['logging'])
            if 'scheduler' in config_data: self._update_dataclass(self.scheduler_config, config_data['scheduler'])
            if 'signin' in config_data: self._update_dataclass(self.signin_config, config_data['signin'])
                
        except Exception as e:
            print(f"从文件加载配置失败: {e}")
            raise
    
    def _load_from_env(self):
        """从环境变量加载配置 (支持所有配置项)"""
        
        # --- Helper Functions ---
        def get_env(key: str, default: Any = None) -> Optional[str]:
            return os.getenv(key, default)

        def get_bool(key: str) -> Optional[bool]:
            val = get_env(key)
            if val is not None:
                return val.lower() == 'true'
            return None

        def get_int(key: str) -> Optional[int]:
            val = get_env(key)
            if val is not None and val.isdigit():
                return int(val)
            return None

        def get_float(key: str) -> Optional[float]:
            val = get_env(key)
            if val is not None:
                try:
                    return float(val)
                except ValueError:
                    return None
            return None

        def get_list(key: str) -> Optional[List[str]]:
            val = get_env(key)
            if val is not None:
                # 假设列表用逗号分隔，且去除空项
                return [item.strip() for item in val.split(',') if item.strip()]
            return None

        # --- 1. Forum Config (API) ---
        if not self.forum_config.session_cookie and get_env("FORUM_SESSION_COOKIE"):
            self.forum_config.session_cookie = get_env("FORUM_SESSION_COOKIE")
            print("从环境变量加载初始Cookie。")
        
        if get_env("FORUM_BASE_URL"): self.forum_config.base_url = get_env("FORUM_BASE_URL")
        if get_env("FORUM_USER_AGENT"): self.forum_config.user_agent = get_env("FORUM_USER_AGENT")
        if get_int("FORUM_REQUEST_TIMEOUT"): self.forum_config.request_timeout = get_int("FORUM_REQUEST_TIMEOUT")
        if get_int("FORUM_MAX_RETRIES"): self.forum_config.max_retries = get_int("FORUM_MAX_RETRIES")
        if get_int("FORUM_RATE_LIMIT_PER_MINUTE"): self.forum_config.rate_limit_per_minute = get_int("FORUM_RATE_LIMIT_PER_MINUTE")
        if get_bool("FORUM_ENABLE_PROXY") is not None: self.forum_config.enable_proxy = get_bool("FORUM_ENABLE_PROXY")
        if get_env("FORUM_PROXY_URL"): self.forum_config.proxy_url = get_env("FORUM_PROXY_URL")

        # --- 2. AI Config ---
        if get_env("AI_PROVIDER"): self.ai_config.provider = get_env("AI_PROVIDER")
        if get_env("AI_API_KEY"): self.ai_config.api_key = get_env("AI_API_KEY")
        if get_env("AI_BASE_URL"): self.ai_config.base_url = get_env("AI_BASE_URL")
        if get_env("AI_MODEL"): self.ai_config.model = get_env("AI_MODEL")
        if get_int("AI_MAX_TOKENS"): self.ai_config.max_tokens = get_int("AI_MAX_TOKENS")
        if get_float("AI_TEMPERATURE"): self.ai_config.temperature = get_float("AI_TEMPERATURE")

        # --- 3. Reply Config ---
        if get_bool("REPLY_ENABLED") is not None: self.reply_config.enabled = get_bool("REPLY_ENABLED")
        if get_float("REPLY_PROBABILITY"): self.reply_config.reply_probability = get_float("REPLY_PROBABILITY")
        if get_int("REPLY_MIN_DELAY_SECONDS"): self.reply_config.min_delay_seconds = get_int("REPLY_MIN_DELAY_SECONDS")
        if get_int("REPLY_MAX_DELAY_SECONDS"): self.reply_config.max_delay_seconds = get_int("REPLY_MAX_DELAY_SECONDS")
        if get_int("REPLY_MAX_REPLIES_PER_HOUR"): self.reply_config.max_replies_per_hour = get_int("REPLY_MAX_REPLIES_PER_HOUR")
        if get_int("REPLY_MAX_REPLIES_PER_DAY"): self.reply_config.max_replies_per_day = get_int("REPLY_MAX_REPLIES_PER_DAY")
        if get_int("REPLY_MAX_LENGTH"): self.reply_config.max_length = get_int("REPLY_MAX_LENGTH")
        if get_int("REPLY_MIN_LENGTH"): self.reply_config.min_length = get_int("REPLY_MIN_LENGTH")
        if get_bool("REPLY_ENABLE_EMOJI") is not None: self.reply_config.enable_emoji = get_bool("REPLY_ENABLE_EMOJI")
        if get_bool("REPLY_TEMPLATE_FALLBACK") is not None: self.reply_config.template_fallback = get_bool("REPLY_TEMPLATE_FALLBACK")

        # --- 4. Filter Config ---
        if get_int("FILTER_MIN_POST_AGE_MINUTES"): self.filter_config.min_post_age_minutes = get_int("FILTER_MIN_POST_AGE_MINUTES")
        if get_int("FILTER_MAX_POST_AGE_HOURS"): self.filter_config.max_post_age_hours = get_int("FILTER_MAX_POST_AGE_HOURS")
        if get_list("FILTER_EXCLUDED_KEYWORDS"): self.filter_config.excluded_keywords = get_list("FILTER_EXCLUDED_KEYWORDS")
        if get_list("FILTER_REQUIRED_KEYWORDS"): self.filter_config.required_keywords = get_list("FILTER_REQUIRED_KEYWORDS")
        if get_int("FILTER_MIN_CONTENT_LENGTH"): self.filter_config.min_content_length = get_int("FILTER_MIN_CONTENT_LENGTH")
        if get_int("FILTER_MAX_CONTENT_LENGTH"): self.filter_config.max_content_length = get_int("FILTER_MAX_CONTENT_LENGTH")
        if get_list("FILTER_EXCLUDED_CATEGORIES"): self.filter_config.excluded_categories = get_list("FILTER_EXCLUDED_CATEGORIES")

        # --- 5. Database Config ---
        if get_env("DATABASE_PATH"): self.database_config.path = get_env("DATABASE_PATH")
        if get_bool("DATABASE_BACKUP_ENABLED") is not None: self.database_config.backup_enabled = get_bool("DATABASE_BACKUP_ENABLED")
        if get_int("DATABASE_BACKUP_INTERVAL_HOURS"): self.database_config.backup_interval_hours = get_int("DATABASE_BACKUP_INTERVAL_HOURS")

        # --- 6. Logging Config ---
        if get_env("LOGGING_LEVEL"): self.logging_config.level = get_env("LOGGING_LEVEL")
        if get_env("LOGGING_FILE_PATH"): self.logging_config.file_path = get_env("LOGGING_FILE_PATH")
        if get_env("LOGGING_MAX_FILE_SIZE"): self.logging_config.max_file_size = get_env("LOGGING_MAX_FILE_SIZE")
        if get_int("LOGGING_BACKUP_COUNT"): self.logging_config.backup_count = get_int("LOGGING_BACKUP_COUNT")

        # --- 7. Scheduler Config ---
        if get_env("SCHEDULER_RUN_MODE"): self.scheduler_config.run_mode = get_env("SCHEDULER_RUN_MODE")
        if get_env("SCHEDULER_START_TIME"): self.scheduler_config.start_time = get_env("SCHEDULER_START_TIME")
        if get_int("SCHEDULER_RUNS_PER_DAY"): self.scheduler_config.runs_per_day = get_int("SCHEDULER_RUNS_PER_DAY")
        if get_int("SCHEDULER_TIME_BETWEEN_RUNS_MIN"): self.scheduler_config.time_between_runs_minutes_min = get_int("SCHEDULER_TIME_BETWEEN_RUNS_MIN")
        if get_int("SCHEDULER_TIME_BETWEEN_RUNS_MAX"): self.scheduler_config.time_between_runs_minutes_max = get_int("SCHEDULER_TIME_BETWEEN_RUNS_MAX")
        if get_int("SCHEDULER_MIN_POST_INTERVAL_SECONDS"): self.scheduler_config.min_post_interval_seconds = get_int("SCHEDULER_MIN_POST_INTERVAL_SECONDS")
        if get_int("SCHEDULER_MAX_POST_INTERVAL_SECONDS"): self.scheduler_config.max_post_interval_seconds = get_int("SCHEDULER_MAX_POST_INTERVAL_SECONDS")

        # --- 8. SignIn Config ---
        if get_bool("SIGNIN_ENABLED") is not None: self.signin_config.enabled = get_bool("SIGNIN_ENABLED")
        if get_bool("SIGNIN_RANDOM_BONUS") is not None: self.signin_config.random_bonus = get_bool("SIGNIN_RANDOM_BONUS")
        if get_bool("SIGNIN_HEADLESS") is not None: self.signin_config.headless = get_bool("SIGNIN_HEADLESS")

    
    def _update_dataclass(self, obj: Any, data: Dict[str, Any]):
        """更新数据类对象"""
        for key, value in data.items():
            if hasattr(obj, key):
                setattr(obj, key, value)
    
    def _validate_config(self):
        """验证配置"""
        if not self.forum_config.session_cookie:
            print("警告: 最终未能加载到任何有效的论坛 Session Cookie！请检查 docker-compose.yml 或 cookie.json 文件。")
        
        if not self.ai_config.api_key:
            print("警告: AI API密钥未设置")
        
        if self.reply_config.max_length < self.reply_config.min_length: raise ValueError("回复最大长度不能小于最小长度")
        if self.reply_config.max_length > 10: print("警告: 回复最大长度超过10字，建议设置为10字以内")
        if self.reply_config.max_delay_seconds < self.reply_config.min_delay_seconds: raise ValueError("最大延迟不能小于最小延迟")

    def save_config(self):
        """保存配置到文件"""
        try:
            config_data = {
                'api': asdict(self.forum_config),
                'ai': asdict(self.ai_config),
                'reply': asdict(self.reply_config),
                'filter': asdict(self.filter_config),
                'database': asdict(self.database_config),
                'logging': asdict(self.logging_config),
                'scheduler': asdict(self.scheduler_config),
                'signin': asdict(self.signin_config)
            }
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
            print(f"配置保存成功: {self.config_file}")
        except Exception as e:
            print(f"保存配置失败: {e}")
            raise

    def get_forum_config(self) -> ForumConfig: return self.forum_config
    def get_ai_config(self) -> AIConfig: return self.ai_config
    def get_reply_config(self) -> ReplyConfig: return self.reply_config
    def get_filter_config(self) -> FilterConfig: return self.filter_config
    def get_database_config(self) -> DatabaseConfig: return self.database_config
    def get_logging_config(self) -> LoggingConfig: return self.logging_config
    def get_scheduler_config(self) -> "SchedulerConfig": return self.scheduler_config
    def get_signin_config(self) -> "SignInConfig": return self.signin_config
    
    def get_config(self) -> Any:
        from types import SimpleNamespace
        config = SimpleNamespace()
        config.forum = self.forum_config
        ai_ns = SimpleNamespace()
        ai_ns.short_reply = self.ai_config
        config.ai = ai_ns
        config.reply = self.reply_config
        config.database = self.database_config
        config.filter = self.filter_config
        config.logging = self.logging_config
        config.scheduler = self.scheduler_config
        config.signin = self.signin_config
        return config

    def update_config(self, section: str, key: str, value: Any):
        config_map = {
            'forum': self.forum_config,
            'ai': self.ai_config,
            'reply': self.reply_config,
            'filter': self.filter_config,
            'database': self.database_config,
            'logging': self.logging_config,
            'scheduler': self.scheduler_config,
            'signin': self.signin_config
        }
        if section in config_map:
            config_obj = config_map[section]
            if hasattr(config_obj, key):
                setattr(config_obj, key, value)
                print(f"配置更新: {section}.{key} = {value}")
            else: raise ValueError(f"配置项不存在: {section}.{key}")
        else: raise ValueError(f"配置节不存在: {section}")

    def get_config_summary(self) -> Dict[str, Any]:
        return {
            'forum': {'base_url': self.forum_config.base_url,'has_cookie': bool(self.forum_config.session_cookie),'rate_limit': self.forum_config.rate_limit_per_minute},
            'ai': {'provider': self.ai_config.provider,'model': self.ai_config.model,'base_url': self.ai_config.base_url,'has_api_key': bool(self.ai_config.api_key)},
            'reply': {'enabled': self.reply_config.enabled,'length_range': f"{self.reply_config.min_length}-{self.reply_config.max_length}",'delay_range': f"{self.reply_config.min_delay_seconds}-{self.reply_config.max_delay_seconds}s",'max_per_hour': self.reply_config.max_replies_per_hour}
        }

    @staticmethod
    def create_default_config(file_path: str):
        """创建默认配置文件"""
        manager = ConfigManager(file_path)
        manager.save_config()


_config_manager = None
def get_config_manager(config_file: str = "config/forum_config.json") -> ConfigManager:
    global _config_manager
    if _config_manager is None: _config_manager = ConfigManager(config_file)
    return _config_manager

def reload_config():
    global _config_manager
    if _config_manager: _config_manager.load_config()

if __name__ == "__main__":
    config = ConfigManager()
    print("配置摘要:")
    summary = config.get_config_summary()
    for section, data in summary.items(): print(f"  {section}: {data}")
