"""
核心调度器
负责整个自动回复流程的协调和执行
"""

import asyncio
import random
import logging
import os
from typing import List, Dict, Any

from ..config.config_manager import ConfigManager, ForumConfig
from ..api.api_wrapper import APIWrapper
from ..ai.content_analyzer import ContentAnalyzer
from ..ai.short_reply_generator import ShortReplyGenerator, ShortReplyConfig
from ..ai.quality_checker import QualityChecker
from ..database.database import DatabaseManager
from ..api.deepflood_client import DeepFloodClient
from ..scheduler.signin_manager import SignInManager

# 配置日志记录
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("forum_reply.log", encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


class ReplyScheduler:
    """论坛自动回复调度器"""

    def __init__(self, config_path: str):
        self.config_manager = ConfigManager(config_path)
        self.config = self.config_manager.get_config()
        
        # 创建 DeepFloodClient 实例
        api_client = DeepFloodClient(self.config.forum)
        self.api_wrapper = APIWrapper(api_client)
        self.content_analyzer = ContentAnalyzer()
        # 创建 ShortReplyConfig 实例
        ai_conf = self.config.ai.short_reply
        short_reply_conf = ShortReplyConfig(
            api_key=ai_conf.api_key,
            base_url=ai_conf.base_url,
            model=ai_conf.model,
            max_length=self.config.reply.max_length,
            min_length=self.config.reply.min_length,
            temperature=ai_conf.temperature,
            max_tokens=ai_conf.max_tokens
        )
        self.short_reply_generator = ShortReplyGenerator(short_reply_conf)
        self.quality_checker = QualityChecker()
        self.db_manager = DatabaseManager(self.config.database.path)
        
        self.run_stats = {
            "posts_found": 0,
            "posts_processed": 0,
            "replies_sent": 0,
            "errors_count": 0,
            "skipped_count": 0
        }
        self.signin_result = "未执行"
        self.replied_posts_details = []

    async def initialize(self):
        """初始化所有组件"""
        logger.info("正在初始化调度器...")
        await self.db_manager.initialize()
        logger.info("数据库初始化完成。")
        logger.info("调度器初始化完成。")

    async def run_single_cycle(self):
        """运行一个完整的工作周期"""
        logger.info("="*50)
        logger.info("开始新一轮自动回复周期...")

        logger.info("步骤 0: 执行每日签到 (并自动刷新Cookie)...")
        signin_manager = None
        if self.config.signin.enabled:
            try:
                # 初始化 SignInManager 时传入 Cookie 文件路径
                signin_manager = SignInManager(
                    cookie=self.config.forum.session_cookie,
                    random_bonus=self.config.signin.random_bonus,
                    headless=self.config.signin.headless,
                    cookie_file_path=self.config.forum.cookie_file_path
                )
                
                # 在异步函数中运行同步的浏览器操作
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, signin_manager.run_signin)
                self.signin_result = "每日签到成功完成，并已刷新Cookie。"
                logger.info("每日签到完成，并已刷新Cookie。")
            except Exception as e:
                self.signin_result = f"执行签到或刷新Cookie时发生错误: {e}"
                logger.error(f"执行签到或刷新Cookie时发生错误: {e}", exc_info=True)
            finally:
                if signin_manager:
                    logger.info("正在关闭签到浏览器...")
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(None, signin_manager.quit)
        else:
            self.signin_result = "签到功能已禁用，跳过签到和Cookie刷新。"
            logger.info("签到功能已禁用，跳过签到和Cookie刷新。")
        
        log_id = await self.db_manager.start_run_log()
        self._reset_stats()

        try:
            # 1. 获取最新帖子
            logger.info("步骤 1: 从RSS源获取最新帖子...")
            latest_posts = await self.api_wrapper.safe_get_post_list()
            if not latest_posts:
                logger.warning("未能获取到任何帖子，或API返回为空。")
                await self.db_manager.end_run_log(log_id, 'completed', log_message="No posts found.")
                return
            
            self.run_stats["posts_found"] = len(latest_posts)
            logger.info(f"获取到 {len(latest_posts)} 个帖子。")

            # 2. 筛选未处理的帖子
            new_posts = []
            for post in latest_posts:
                if not await self.db_manager.is_post_processed(post['post_id']):
                    new_posts.append(post)
            
            if not new_posts:
                logger.info("没有需要处理的新帖子。")
                await self.db_manager.end_run_log(log_id, 'completed', posts_found=self.run_stats["posts_found"])
                return
            
            logger.info(f"发现 {len(new_posts)} 个新帖子需要处理。")

            # 3. 检查每日回复限额
            daily_limit = self.config.reply.max_replies_per_day
            replies_today = await self.db_manager.count_replies_today()
            remaining_replies = daily_limit - replies_today
            
            logger.info(f"每日回复限额: {daily_limit}。今日已回复: {replies_today}。剩余额度: {remaining_replies}。")

            if remaining_replies <= 0:
                logger.info("已达到每日回复数量上限，今日不再回复。")
                await self.db_manager.end_run_log(log_id, 'completed', posts_found=self.run_stats["posts_found"], log_message="Daily reply limit reached.")
                return

            # 4. 截取需要处理的帖子
            posts_to_process = new_posts[:remaining_replies]
            logger.info(f"根据剩余额度，本轮将尝试处理 {len(posts_to_process)} 个帖子。")


            # 5. 依次处理新帖子
            for post_summary in posts_to_process:
                await self._process_single_post(post_summary)
                
                # 随机延迟，模拟人类行为
                delay = random.uniform(
                    self.config.scheduler.min_post_interval_seconds,
                    self.config.scheduler.max_post_interval_seconds
                )
                logger.info(f"处理完一个帖子，延迟 {delay:.2f} 秒...")
                await asyncio.sleep(delay)

            logger.info("本轮所有新帖子处理完毕。")

        except Exception as e:
            logger.error(f"周期运行中发生严重错误: {e}", exc_info=True)
            self.run_stats["errors_count"] += 1
            log_params = {
                "posts_found": self.run_stats.get("posts_found", 0),
                "replies_sent": self.run_stats.get("replies_sent", 0),
                "errors_count": self.run_stats.get("errors_count", 0)
            }
            await self.db_manager.end_run_log(log_id, 'failed', **log_params, log_message=str(e))
        else:
            logger.info("周期运行成功结束。")
            log_params = {
                "posts_found": self.run_stats.get("posts_found", 0),
                "replies_sent": self.run_stats.get("replies_sent", 0),
                "errors_count": self.run_stats.get("errors_count", 0)
            }
            await self.db_manager.end_run_log(log_id, 'completed', **log_params, log_message="Cycle completed successfully.")
        
        notification_payload = {
            "signin_result": self.signin_result,
            "replied_posts": self.replied_posts_details,
            "stats": self.run_stats.copy()
        }
        
        logger.info(f"本周期统计: {self.run_stats}")
        logger.info("="*50)
        return notification_payload

    async def _process_single_post(self, post_summary: Dict[str, Any]):
        """处理单个帖子"""
        post_id = post_summary['post_id']
        post_title = post_summary['title']
        logger.info(f"\n--- 开始处理帖子 ID: {post_id}, 标题: {post_title} ---")
        self.run_stats["posts_processed"] += 1

        try:
            # 标记为待处理
            await self.db_manager.add_processed_post(post_id, post_title, 'pending')

            # 获取帖子详情
            post_detail = await self.api_wrapper.safe_get_post_detail(post_id)
            if not post_detail:
                logger.error(f"无法获取帖子 {post_id} 的详细信息。")
                await self.db_manager.update_post_status(post_id, 'failed', "Failed to get post detail")
                self.run_stats["errors_count"] += 1
                return

            # 内容分析
            analysis = self.content_analyzer.analyze(post_detail.title, post_detail.content)
            logger.info(f"帖子内容分析结果: 类别='{analysis.category}', 情感='{analysis.sentiment}'")

            # 生成回复
            reply_content = await self.short_reply_generator.generate_reply(post_detail.title, post_detail.content)
            logger.info(f"AI生成回复: '{reply_content}'")

            # 发送回复
            success, message = await self.api_wrapper.safe_post_comment(post_id, reply_content)
            if success:
                logger.info(f"成功向帖子 {post_id} 发送回复。")
                self.replied_posts_details.append({
                    "title": post_title,
                    "reply_content": reply_content
                })
                await self.db_manager.update_post_status(post_id, 'replied')
                await self.db_manager.add_reply_history(
                    post_id=post_id,
                    reply_content=reply_content,
                    quality_score=1.0,
                    ai_provider=self.config.ai.short_reply.provider,
                    ai_model=self.config.ai.short_reply.model,
                    is_fallback=False
                )
                self.run_stats["replies_sent"] += 1
            else:
                logger.error(f"向帖子 {post_id} 发送回复失败: {message}")
                await self.db_manager.update_post_status(post_id, 'failed', f"API post comment failed: {message}")
                self.run_stats["errors_count"] += 1

        except Exception as e:
            logger.error(f"处理帖子 {post_id} 时发生错误: {e}", exc_info=True)
            await self.db_manager.update_post_status(post_id, 'failed', str(e))
            self.run_stats["errors_count"] += 1

    def _reset_stats(self):
        """重置本轮运行统计"""
        self.run_stats = {
            "posts_found": 0,
            "posts_processed": 0,
            "replies_sent": 0,
            "errors_count": 0,
            "skipped_count": 0
        }
        self.signin_result = "未执行"
        self.replied_posts_details = []

async def main():
    """用于测试调度器的主函数"""
    config_file = "config/forum_config.json"
    if not os.path.exists(config_file):
        logger.error(f"配置文件 {config_file} 不存在。请先创建。")
        return

    scheduler = ReplyScheduler(config_path=config_file)
    await scheduler.initialize()
    await scheduler.run_single_cycle()

if __name__ == "__main__":
    pass
