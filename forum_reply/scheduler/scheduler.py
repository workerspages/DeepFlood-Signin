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
from ..database.database import DatabaseManager
from ..api.deepflood_client import DeepFloodClient
from ..scheduler.signin_manager import SignInManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', handlers=[logging.StreamHandler(), logging.FileHandler("forum_reply.log", encoding='utf-8')])
logger = logging.getLogger(__name__)

class ReplyScheduler:
    """论坛自动回复调度器"""
    def __init__(self, config_path: str):
        self.config_manager = ConfigManager(config_path)
        self.config = self.config_manager.get_config()
        self.api_client = DeepFloodClient(self.config.forum)
        self.api_wrapper = APIWrapper(self.api_client)
        self.content_analyzer = ContentAnalyzer()
        ai_conf = self.config.ai.short_reply
        short_reply_conf = ShortReplyConfig(api_key=ai_conf.api_key, base_url=ai_conf.base_url, model=ai_conf.model, max_length=self.config.reply.max_length, min_length=self.config.reply.min_length, temperature=ai_conf.temperature, max_tokens=ai_conf.max_tokens)
        self.short_reply_generator = ShortReplyGenerator(short_reply_conf)
        self.db_manager = DatabaseManager(self.config.database.path)
        self._reset_stats()

    async def initialize(self):
        logger.info("正在初始化调度器...")
        await self.db_manager.initialize()
        logger.info("数据库初始化完成。")

    async def run_single_cycle(self):
        logger.info("="*50)
        logger.info("开始新一轮自动回复周期...")
        self._reset_stats()
        
        driver = None
        loop = asyncio.get_running_loop()
        try:
            # 【重要修改】在周期开始时，只创建一次浏览器实例
            logger.info("步骤 0: 初始化共享浏览器实例 (并自动刷新Cookie)...")
            driver = await loop.run_in_executor(None, self.api_client.setup_driver)
            if not driver:
                raise Exception("共享浏览器实例初始化失败，任务中止。")
            
            # 执行签到
            if self.config.signin.enabled:
                signin_manager = SignInManager(random_bonus=self.config.signin.random_bonus)
                await loop.run_in_executor(None, signin_manager.run_signin, driver)
                self.signin_result = "每日签到成功完成。"
            else:
                self.signin_result = "签到功能已禁用。"
            
            log_id = await self.db_manager.start_run_log()
            
            # 获取帖子
            logger.info("步骤 1: 从RSS源获取最新帖子...")
            latest_posts = await self.api_wrapper.safe_get_post_list()
            if not latest_posts:
                logger.warning("未能获取到任何帖子。")
                await self.db_manager.end_run_log(log_id, 'completed', log_message="No posts found.")
                return

            self.run_stats["posts_found"] = len(latest_posts)
            new_posts = [p for p in latest_posts if not await self.db_manager.is_post_processed(p['post_id'])]
            if not new_posts:
                logger.info("没有需要处理的新帖子。")
                await self.db_manager.end_run_log(log_id, 'completed', posts_found=self.run_stats["posts_found"])
                return
            
            # 处理帖子
            daily_limit = self.config.reply.max_replies_per_day
            replies_today = await self.db_manager.count_replies_today()
            posts_to_process = new_posts[:(daily_limit - replies_today)]
            
            for post_summary in posts_to_process:
                # 【重要修改】将共享的 driver 实例传递下去
                await self._process_single_post(post_summary, driver)
                delay = random.uniform(self.config.scheduler.min_post_interval_seconds, self.config.scheduler.max_post_interval_seconds)
                await asyncio.sleep(delay)
            
            await self.db_manager.end_run_log(log_id, 'completed', **self.run_stats)

        except Exception as e:
            logger.error(f"周期运行中发生严重错误: {e}", exc_info=True)
            self.run_stats["errors_count"] += 1
        finally:
            # 【重要修改】在所有任务结束后，统一关闭浏览器
            if driver:
                logger.info("所有任务完成，正在关闭共享浏览器实例...")
                await loop.run_in_executor(None, driver.quit)
        
        notification_payload = {"signin_result": self.signin_result, "replied_posts": self.replied_posts_details, "stats": self.run_stats.copy()}
        logger.info(f"本周期统计: {self.run_stats}")
        return notification_payload

    async def _process_single_post(self, post_summary: Dict[str, Any], driver):
        post_id, post_title = post_summary['post_id'], post_summary['title']
        logger.info(f"\n--- 开始处理帖子 ID: {post_id}, 标题: {post_title} ---")
        self.run_stats["posts_processed"] += 1
        loop = asyncio.get_running_loop()
        try:
            await self.db_manager.add_processed_post(post_id, post_title, 'pending')

            # 【重要修改】使用共享的 driver 实例获取详情
            post_detail = await loop.run_in_executor(None, self.api_client.get_post_detail, post_id, driver)
            if not post_detail:
                raise Exception("获取帖子详情失败")

            analysis = self.content_analyzer.analyze(post_detail.title, post_detail.content)
            reply_content = await self.short_reply_generator.generate_reply(post_detail.title, post_detail.content)
            
            # 【新增】打印 AI 生成的回复内容，以便在日志中查看
            logger.info(f"AI 拟定回复内容: \"{reply_content}\"")
            
            # 【重要修改】使用共享的 driver 实例发送回复
            success, message = await loop.run_in_executor(None, self.api_client.post_comment, post_id, reply_content, driver)
            if success:
                # 【新增】发送成功确认日志
                logger.info(f"✅ 回复发送成功 (ID: {post_id})")
                self.replied_posts_details.append({"title": post_title, "reply_content": reply_content})
                await self.db_manager.update_post_status(post_id, 'replied')
                await self.db_manager.add_reply_history(post_id=post_id, reply_content=reply_content, ai_provider=self.config.ai.short_reply.provider, ai_model=self.config.ai.short_reply.model)
                self.run_stats["replies_sent"] += 1
            else:
                raise Exception(f"发送回复失败: {message}")

        except Exception as e:
            logger.error(f"处理帖子 {post_id} 时发生错误: {e}")
            await self.db_manager.update_post_status(post_id, 'failed', str(e))
            self.run_stats["errors_count"] += 1

    def _reset_stats(self):
        self.run_stats = {"posts_found": 0, "posts_processed": 0, "replies_sent": 0, "errors_count": 0, "skipped_count": 0}
        self.signin_result = "未执行"
        self.replied_posts_details = []
