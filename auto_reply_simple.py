"""
简化版自动回复脚本
参照test_rss_ai_reply.py，直接从RSS获取帖子并生成回复，支持实际发送
"""

import requests
import xml.etree.ElementTree as ET
import logging
import time
import re
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from forum_reply.config.config_manager import ConfigManager
from forum_reply.api.deepflood_client import DeepFloodClient
from forum_reply.api.api_wrapper import APIWrapper
from forum_reply.ai.short_reply_generator import create_reply_bot_from_config

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def fetch_rss_posts(rss_url: str, max_posts: int = 10):
    """从RSS源获取帖子"""
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"正在获取RSS源: {rss_url}")
        response = requests.get(rss_url, timeout=30)
        response.raise_for_status()
        
        # 解析XML
        root = ET.fromstring(response.content)
        
        posts = []
        items = root.findall('.//item')[:max_posts]
        
        for item in items:
            title_elem = item.find('title')
            description_elem = item.find('description')
            link_elem = item.find('link')
            pubdate_elem = item.find('pubDate')
            
            title = title_elem.text if title_elem is not None else "无标题"
            description = description_elem.text if description_elem is not None else "无内容"
            link = link_elem.text if link_elem is not None else ""
            pubdate = pubdate_elem.text if pubdate_elem is not None else ""
            
            # 清理HTML标签
            description = re.sub(r'<[^>]+>', '', description)
            description = description.strip()
            
            # 从链接中提取帖子ID
            post_id = extract_post_id_from_url(link)
            
            posts.append({
                'post_id': post_id,
                'title': title,
                'content': description,
                'link': link,
                'pubdate': pubdate
            })
        
        logger.info(f"成功获取 {len(posts)} 个帖子")
        return posts
        
    except Exception as e:
        logger.error(f"获取RSS源失败: {e}")
        return []

def extract_post_id_from_url(url: str) -> Optional[int]:
    """从URL中提取帖子ID"""
    match = re.search(r'/post-(\d+)-', url)
    return int(match.group(1)) if match else None

def should_reply_to_post(post: Dict) -> Tuple[bool, str]:
    """判断是否应该回复此帖子"""
    title = post.get('title', '').lower()
    content = post.get('content', '').lower()
    
    # 跳过的关键词
    skip_keywords = ['广告', '推广', '加群', '微信', 'qq', '代理', '刷单', '兼职']
    if any(keyword in title or keyword in content for keyword in skip_keywords):
        return False, "包含广告关键词"
    
    # 跳过过短的标题
    # if len(post.get('title', '')) < 5:
    #     return False, "标题过短"
    
    # 跳过过短的内容
    # if len(post.get('content', '')) < 10:
    #     return False, "内容过短"
    
    # 跳过没有帖子ID的
    if not post.get('post_id'):
        return False, "无法获取帖子ID"
    
    return True, "符合回复条件"

def generate_ai_reply_with_retry(reply_bot, title: str, content: str, max_retries: int = 2) -> Optional[str]:
    """生成AI回复（带重试机制）"""
    logger = logging.getLogger(__name__)
    
    for attempt in range(max_retries + 1):
        try:
            logger.info(f"尝试生成AI回复 (第{attempt + 1}次)")
            
            # 生成回复
            reply, analysis = reply_bot.generate_reply_for_post(title, content)
            
            # 检查回复是否有效
            if reply and reply.strip() and len(reply.strip()) > 0:
                logger.info(f"AI回复生成成功: \"{reply}\" (分类: {analysis.category}, 情感: {analysis.sentiment})")
                return reply.strip()
            else:
                logger.warning(f"AI生成的回复为空或无效: \"{reply}\"")
                
        except Exception as e:
            logger.error(f"AI回复生成失败: {e}")
        
        # 如果不是最后一次尝试，等待后重试
        if attempt < max_retries:
            wait_time = 3 * (attempt + 1)  # 递增等待时间
            logger.info(f"等待 {wait_time} 秒后重试...")
            time.sleep(wait_time)
    
    logger.error("AI回复生成最终失败")
    return None

def auto_reply_main(max_posts: int = 3, dry_run: bool = True):
    """主要的自动回复流程"""
    logger = logging.getLogger(__name__)
    
    print("=" * 80)
    print("自动回复测试")
    print(f"模式: {'测试模式 (不实际发送)' if dry_run else '实际发送模式'}")
    print("=" * 80)
    
    # 1. 获取RSS帖子
    rss_url = "https://feed.deepflood.com/topic.rss.xml"
    posts = fetch_rss_posts(rss_url, max_posts)
    
    if not posts:
        logger.error("无法获取RSS帖子，测试终止")
        return
    
    # 2. 加载配置
    try:
        config_manager = ConfigManager("config/forum_config.json")
        ai_config = config_manager.get_ai_config()
        forum_config = config_manager.get_forum_config()
        logger.info("配置文件加载成功")
    except Exception as e:
        logger.error(f"加载配置文件失败: {e}")
        return
    
    # 3. 初始化AI回复机器人
    try:
        reply_bot = create_reply_bot_from_config(ai_config)
        logger.info("AI回复机器人初始化成功")
        logger.info(f"使用模型: {ai_config.model}")
        logger.info(f"API地址: {ai_config.base_url}")
    except Exception as e:
        logger.error(f"初始化AI回复机器人失败: {e}")
        return
    
    # 4. 初始化论坛客户端（用于发送回复）
    api_wrapper = None
    if not dry_run:
        try:
            forum_client = DeepFloodClient(forum_config)
            api_wrapper = APIWrapper(forum_client, rate_limit_per_minute=10)
            logger.info("论坛API客户端初始化成功")
        except Exception as e:
            logger.error(f"初始化论坛API客户端失败: {e}")
            return
    
    # 5. 处理帖子
    results = []
    for i, post in enumerate(posts, 1):
        print(f"\n{'-' * 60}")
        print(f"帖子 {i}/{len(posts)}")
        print(f"{'-' * 60}")
        print(f"标题: {post['title']}")
        print(f"内容: {post['content'][:200]}{'...' if len(post['content']) > 200 else ''}")
        print(f"帖子ID: {post['post_id']}")
        print(f"链接: {post['link']}")
        
        result = {
            'post_id': post['post_id'],
            'title': post['title'],
            'ai_reply': None,
            'reply_sent': False,
            'error': None,
            'skipped': False,
            'skip_reason': None
        }
        
        try:
            # 检查是否应该回复
            should_reply, reason = should_reply_to_post(post)
            if not should_reply:
                logger.info(f"跳过帖子: {reason}")
                result['skipped'] = True
                result['skip_reason'] = reason
                results.append(result)
                continue
            
            # 生成AI回复
            logger.info("正在生成AI回复...")
            ai_reply = generate_ai_reply_with_retry(reply_bot, post['title'], post['content'])
            
            if not ai_reply:
                logger.error("AI回复生成失败，跳过此帖子")
                result['error'] = "AI回复生成失败"
                results.append(result)
                continue
            
            result['ai_reply'] = ai_reply
            print(f"\nAI生成回复: \"{ai_reply}\"")
            
            # 发送回复
            if dry_run:
                logger.info(f"[测试模式] 将要发送的回复: \"{ai_reply}\"")
                result['reply_sent'] = True  # 测试模式下标记为成功
            else:
                logger.info(f"正在发送回复: \"{ai_reply}\"")
                success, message = api_wrapper.safe_post_comment(post['post_id'], ai_reply)
                
                if success:
                    logger.info(f"回复发送成功: {message}")
                    result['reply_sent'] = True
                else:
                    logger.error(f"回复发送失败: {message}")
                    result['error'] = f"发送失败: {message}"
            
            results.append(result)
            
            # 添加延迟避免过于频繁
            if i < len(posts):
                delay = 8 if not dry_run else 3
                logger.info(f"等待 {delay} 秒后处理下一个帖子...")
                time.sleep(delay)
                
        except Exception as e:
            logger.error(f"处理帖子时发生错误: {e}")
            result['error'] = str(e)
            results.append(result)
    
    # 6. 统计结果
    print(f"\n{'=' * 80}")
    print("自动回复结果统计")
    print(f"{'=' * 80}")
    
    total_posts = len(results)
    successful_replies = sum(1 for r in results if r['reply_sent'])
    failed_replies = sum(1 for r in results if r['error'])
    skipped_posts = sum(1 for r in results if r['skipped'])
    
    print(f"总帖子数: {total_posts}")
    print(f"成功回复数: {successful_replies}")
    print(f"失败回复数: {failed_replies}")
    print(f"跳过帖子数: {skipped_posts}")
    
    if total_posts > 0:
        success_rate = (successful_replies / total_posts) * 100
        print(f"成功率: {success_rate:.1f}%")
    else:
        print("成功率: 0.0%")
    
    # 详细结果
    print(f"\n详细结果:")
    print(f"{'序号':<4} {'帖子ID':<8} {'标题':<25} {'AI回复':<15} {'状态':<10}")
    print("-" * 70)
    
    for i, result in enumerate(results, 1):
        title_short = result['title'][:23] + ".." if len(result['title']) > 25 else result['title']
        reply_short = (result['ai_reply'][:13] + "..") if result['ai_reply'] and len(result['ai_reply']) > 15 else (result['ai_reply'] or "无")
        
        if result['skipped']:
            status = "跳过"
        elif result['reply_sent']:
            status = "成功"
        else:
            status = "失败"
        
        print(f"{i:<4} {result['post_id']:<8} {title_short:<25} {reply_short:<15} {status:<10}")
    
    # 保存结果
    try:
        import json
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"auto_reply_results_{timestamp}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"\n结果已保存到: {filename}")
        
    except Exception as e:
        logger.warning(f"保存结果文件失败: {e}")
    
    print(f"\n{'=' * 80}")
    print("自动回复完成！")
    print(f"{'=' * 80}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="简化版自动回复脚本")
    parser.add_argument(
        "--max-posts",
        type=int,
        default=3,
        help="最大处理帖子数量 (默认: 3)"
    )
    parser.add_argument(
        "--real-send",
        action="store_true",
        help="实际发送回复 (默认为测试模式)"
    )
    
    args = parser.parse_args()
    
    # 运行自动回复
    auto_reply_main(args.max_posts, dry_run=not args.real_send)