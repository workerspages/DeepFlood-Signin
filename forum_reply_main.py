"""
论坛自动回复功能主入口
负责加载配置、初始化调度器，并根据配置的模式运行。
"""

import asyncio
import argparse
import logging
import time
import random
import datetime
import schedule
from typing import Dict, Any

from forum_reply.scheduler.scheduler import ReplyScheduler
from forum_reply.config.config_manager import ConfigManager
import notify

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("forum_reply.log", encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


def send_notification(report: Dict[str, Any]):
    """格式化并发送通知"""
    # 1. 检查是否有任何通知渠道被配置
    if not notify.is_notification_configured():
        logger.info("未配置任何通知渠道，跳过发送任务报告。")
        return

    if not report:
        logger.warning("任务报告为空，不发送通知。")
        return

    title = "论坛自动回复任务报告"
    
    # 格式化内容
    content = f"任务执行完毕！\n\n"
    content += f"【签到结果】\n{report.get('signin_result', '未知')}\n\n"
    
    stats = report.get('stats', {})
    content += f"【任务统计】\n"
    content += f"- 发现帖子: {stats.get('posts_found', 0)}\n"
    content += f"- 成功回复: {stats.get('replies_sent', 0)}\n"
    content += f"- 失败或错误: {stats.get('errors_count', 0)}\n\n"

    replied_posts = report.get('replied_posts', [])
    if replied_posts:
        content += "【回复详情】\n"
        for i, post in enumerate(replied_posts, 1):
            content += f"{i}. 帖子: {post['title']}\n"
            content += f"   回复: {post['reply_content']}\n"
    else:
        content += "【回复详情】\n本次运行没有回复任何帖子。\n"

    # 发送通知
    try:
        logger.info("正在发送任务报告通知...")
        notify.send(title, content)
        logger.info("任务报告通知发送成功。")
    except Exception as e:
        logger.error(f"发送通知失败: {e}", exc_info=True)


async def run_scheduler_once(config_path: str):
    """单次运行调度器"""
    logger.info("模式: 单次运行。")
    scheduler = ReplyScheduler(config_path)
    await scheduler.initialize()
    report = await scheduler.run_single_cycle()
    logger.info("单次运行完成。")
    return report


def run_scheduler_job(config_path: str):
    """用于 schedule 库调用的同步包装函数"""
    logger.info("计划任务触发，开始执行回复周期...")
    try:
        report = asyncio.run(run_scheduler_once(config_path))
        send_notification(report)
    except Exception as e:
        logger.error(f"计划任务执行期间发生错误: {e}", exc_info=True)
        if notify.is_notification_configured():
            notify.send("论坛回复任务失败", f"执行定时任务时发生严重错误，请检查日志。\n错误信息: {e}")
        else:
            logger.info("未配置任何通知渠道，跳过发送错误通知。")
    logger.info("本轮计划任务执行完毕。")


def run_scheduler_scheduled(config_path: str):
    """定时调度运行"""
    logger.info("模式: 定时调度运行。")
    config = ConfigManager(config_path).get_config()

    start_time_str = config.scheduler.start_time
    
    try:
        # 验证时间格式是否正确
        datetime.datetime.strptime(start_time_str, "%H:%M")
    except (ValueError, AttributeError):
        logger.error(f"配置文件中的启动时间 (start_time: '{start_time_str}') 格式无效。请使用 'HH:MM' 格式。")
        return

    logger.info(f"任务已安排在每天 {start_time_str} 运行。")
    schedule.every().day.at(start_time_str).do(run_scheduler_job, config_path=config_path)

    logger.info("调度器已启动，等待任务触发...")
    
    while True:
        schedule.run_pending()
        time.sleep(1)


def main():
    """主函数入口"""
    parser = argparse.ArgumentParser(description="论坛自动回复机器人")
    parser.add_argument(
        "--config",
        type=str,
        default="config/forum_config.json",
        help="配置文件路径"
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=['once', 'schedule'],
        default=None,
        help="运行模式: 'once' (单次运行) 或 'schedule' (定时调度)。默认为配置文件中的设置。"
    )
    parser.add_argument(
        "--init-config",
        action="store_true",
        help="如果配置文件不存在，则创建一个默认的配置文件。"
    )
    
    args = parser.parse_args()

    if args.init_config:
        logger.info(f"正在检查并创建默认配置文件于: {args.config}")
        ConfigManager.create_default_config(args.config)
        logger.info("配置文件已创建。请根据需要修改配置后重新运行。")
        return

    # 确定运行模式
    run_mode = args.mode
    if not run_mode:
        try:
            config = ConfigManager(args.config).get_config()
            run_mode = config.scheduler.run_mode
        except FileNotFoundError:
            logger.error(f"错误: 配置文件 '{args.config}' 未找到。")
            logger.info(f"请先创建配置文件，或使用 --init-config 参数生成一个默认配置文件。")
            return
        except Exception as e:
            logger.error(f"加载配置文件时出错: {e}")
            return

    if run_mode == 'once':
        report = asyncio.run(run_scheduler_once(args.config))
        send_notification(report)
    elif run_mode == 'schedule':
        run_scheduler_scheduled(args.config)
    else:
        logger.error(f"未知的运行模式: {run_mode}")


if __name__ == "__main__":
    main()