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
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    request_timeout: int = 30
    max_retries: int = 3
    rate_limit_per_minute: int = 20
    enable_proxy: bool = False
    proxy_url: str = ""


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
        """加载配置"""
        load_dotenv()
        try:
            # 首先从文件加载
            if os.path.exists(self.config_file):
                self._load_from_file()
                print(f"配置从文件加载成功: {self.config_file}")
            else:
                print(f"配置文件不存在: {self.config_file}，使用默认配置")
            
            # 然后从环境变量覆盖
            self._load_from_env()
            
            # 验证配置
            self._validate_config()
            
        except Exception as e:
            print(f"加载配置失败: {e}")
            raise
    
    def _load_from_file(self):
        """从JSON文件加载配置"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # 更新各个配置对象
            if 'api' in config_data:
                self._update_dataclass(self.forum_config, config_data['api'])
            
            if 'ai' in config_data:
                self._update_dataclass(self.ai_config, config_data['ai'])
            
            if 'reply' in config_data:
                self._update_dataclass(self.reply_config, config_data['reply'])
            
            if 'filter' in config_data:
                self._update_dataclass(self.filter_config, config_data['filter'])
            
            if 'database' in config_data:
                self._update_dataclass(self.database_config, config_data['database'])
            
            if 'logging' in config_data:
                self._update_dataclass(self.logging_config, config_data['logging'])
            
            if 'scheduler' in config_data:
                self._update_dataclass(self.scheduler_config, config_data['scheduler'])
            
            if 'signin' in config_data:
                self._update_dataclass(self.signin_config, config_data['signin'])
                
        except Exception as e:
            print(f"从文件加载配置失败: {e}")
            raise
    
    def _load_from_env(self):
        """从环境变量加载配置"""
        # 论坛配置
        if os.getenv("FORUM_SESSION_COOKIE"):
            self.forum_config.session_cookie = os.getenv("FORUM_SESSION_COOKIE")
        if os.getenv("FORUM_BASE_URL"):
            self.forum_config.base_url = os.getenv("FORUM_BASE_URL")
        
        # AI配置
        if os.getenv("AI_API_KEY"):
            self.ai_config.api_key = os.getenv("AI_API_KEY")
        if os.getenv("AI_BASE_URL"):
            self.ai_config.base_url = os.getenv("AI_BASE_URL")
        if os.getenv("AI_MODEL"):
            self.ai_config.model = os.getenv("AI_MODEL")
        
        # 回复配置
        if os.getenv("REPLY_ENABLED"):
            self.reply_config.enabled = os.getenv("REPLY_ENABLED").lower() == "true"
        if os.getenv("REPLY_MAX_LENGTH"):
            self.reply_config.max_length = int(os.getenv("REPLY_MAX_LENGTH"))
        if os.getenv("REPLY_MIN_LENGTH"):
            self.reply_config.min_length = int(os.getenv("REPLY_MIN_LENGTH"))
            
        # 调度器配置
        if os.getenv("SCHEDULER_START_TIME"):
            self.scheduler_config.start_time = os.getenv("SCHEDULER_START_TIME")
    
    def _update_dataclass(self, obj: Any, data: Dict[str, Any]):
        """更新数据类对象"""
        for key, value in data.items():
            if hasattr(obj, key):
                setattr(obj, key, value)
    
    def _validate_config(self):
        """验证配置"""
        # 验证必需的配置项
        if not self.forum_config.session_cookie:
            print("警告: 论坛Session Cookie未设置")
        
        if not self.ai_config.api_key:
            print("警告: AI API密钥未设置")
        
        # 验证回复长度配置
        if self.reply_config.max_length < self.reply_config.min_length:
            raise ValueError("回复最大长度不能小于最小长度")
        
        if self.reply_config.max_length > 10:
            print("警告: 回复最大长度超过10字，建议设置为10字以内")
        
        # 验证延迟配置
        if self.reply_config.max_delay_seconds < self.reply_config.min_delay_seconds:
            raise ValueError("最大延迟不能小于最小延迟")
    
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
            
            # 确保目录存在
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
            
            print(f"配置保存成功: {self.config_file}")
            
        except Exception as e:
            print(f"保存配置失败: {e}")
            raise
    
    def get_forum_config(self) -> ForumConfig:
        """获取论坛配置"""
        return self.forum_config
    
    def get_ai_config(self) -> AIConfig:
        """获取AI配置"""
        return self.ai_config
    
    def get_reply_config(self) -> ReplyConfig:
        """获取回复配置"""
        return self.reply_config
    
    def get_filter_config(self) -> FilterConfig:
        """获取过滤配置"""
        return self.filter_config
    
    def get_database_config(self) -> DatabaseConfig:
        """获取数据库配置"""
        return self.database_config
    
    def get_logging_config(self) -> LoggingConfig:
        """获取日志配置"""
        return self.logging_config
    
    def get_scheduler_config(self) -> "SchedulerConfig":
        """获取调度器配置"""
        return self.scheduler_config

    def get_signin_config(self) -> "SignInConfig":
        """获取签到配置"""
        return self.signin_config
 
    def get_config(self) -> Any:
        """返回一个包含所有配置的命名空间对象，以兼容旧代码"""
        from types import SimpleNamespace
        
        config = SimpleNamespace()
        config.forum = self.forum_config
        
        # 兼容旧的 ai.short_reply 结构
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
        """更新配置项"""
        config_map = {
            'forum': self.forum_config,
            'ai': self.ai_config,
            'reply': self.reply_config,
            'filter': self.filter_config,
            'database': self.database_config,
            'logging': self.logging_config
        }
        
        if section in config_map:
            config_obj = config_map[section]
            if hasattr(config_obj, key):
                setattr(config_obj, key, value)
                print(f"配置更新: {section}.{key} = {value}")
            else:
                raise ValueError(f"配置项不存在: {section}.{key}")
        else:
            raise ValueError(f"配置节不存在: {section}")
    
    def get_config_summary(self) -> Dict[str, Any]:
        """获取配置摘要"""
        return {
            'forum': {
                'base_url': self.forum_config.base_url,
                'has_cookie': bool(self.forum_config.session_cookie),
                'rate_limit': self.forum_config.rate_limit_per_minute
            },
            'ai': {
                'provider': self.ai_config.provider,
                'model': self.ai_config.model,
                'base_url': self.ai_config.base_url,
                'has_api_key': bool(self.ai_config.api_key)
            },
            'reply': {
                'enabled': self.reply_config.enabled,
                'length_range': f"{self.reply_config.min_length}-{self.reply_config.max_length}",
                'delay_range': f"{self.reply_config.min_delay_seconds}-{self.reply_config.max_delay_seconds}s",
                'max_per_hour': self.reply_config.max_replies_per_hour
            }
        }


# 全局配置实例
_config_manager = None


def get_config_manager(config_file: str = "config/forum_config.json") -> ConfigManager:
    """获取全局配置管理器实例"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager(config_file)
    return _config_manager


def reload_config():
    """重新加载配置"""
    global _config_manager
    if _config_manager:
        _config_manager.load_config()


if __name__ == "__main__":
    # 测试配置管理器
    config = ConfigManager()
    print("配置摘要:")
    summary = config.get_config_summary()
    for section, data in summary.items():
        print(f"  {section}: {data}")
