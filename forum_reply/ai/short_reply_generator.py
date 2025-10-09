"""
短回复AI生成器
支持1-10字的智能短回复生成，集成new-api项目
"""

import openai
import random
import asyncio
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime

from .content_analyzer import ContentAnalyzer, ContentAnalysis
from ..config.config_manager import AIConfig


@dataclass
class ShortReplyConfig:
    """短回复配置"""
    api_key: str
    base_url: str = "http://localhost:3000/v1"  # new-api项目默认地址
    model: str = "gpt-3.5-turbo"
    max_length: int = 10
    min_length: int = 1
    temperature: float = 0.8
    max_tokens: int = 30


class ShortReplyGenerator:
    """短回复生成器"""
    
    def __init__(self, config: ShortReplyConfig):
        self.config = config
        self.content_analyzer = ContentAnalyzer()
        
        # 初始化OpenAI客户端，使用new-api项目
        self.client = openai.AsyncOpenAI(
            api_key=config.api_key,
            base_url=config.base_url
        )
        
        # 预定义短回复模板库（优化）
        self.reply_templates = {
            "求助问答": {
                "positive": ["试试看", "可以的", "有用", "没问题", "👍"],
                "negative": ["加油", "试试看", "检查下", "别急", "会好的"],
                "neutral": ["试试看", "可以的", "支持", "👍"]
            },
            "技术讨论": {
                "positive": ["赞同", "有道理", "学习了", "不错", "👍"],
                "negative": ["试试看", "检查下", "调试下", "👍"],
                "neutral": ["学习了", "有道理", "收藏", "👍"]
            },
            "生活分享": {
                "positive": ["有意思", "赞", "同感", "不错", "👍"],
                "negative": ["理解", "加油", "会好的", "支持"],
                "neutral": ["有意思", "赞", "同感", "👍"]
            },
            "讨论交流": {
                "positive": ["同意", "有道理", "支持", "👍"],
                "negative": ["理解", "有道理", "支持", "👍"],
                "neutral": ["同意", "有道理", "支持", "👍"]
            },
            "新闻资讯": {
                "positive": ["关注", "收藏", "有用", "👍"],
                "negative": ["关注", "了解", "👍"],
                "neutral": ["关注", "收藏", "👍"]
            },
            "资源分享": {
                "positive": ["感谢", "收藏", "有用", "👍"],
                "negative": ["感谢", "收藏", "👍"],
                "neutral": ["感谢", "收藏", "👍"]
            },
            "通用": {
                "positive": ["👍", "赞", "不错", "支持"],
                "negative": ["加油", "支持", "👍"],
                "neutral": ["👍", "支持", "不错"]
            }
        }
        
        # 情感回复映射
        self.sentiment_replies = {
            "positive": ["赞", "👍", "不错", "支持", "很棒", "厉害"],
            "negative": ["加油", "理解", "支持", "没事的", "会好的"],
            "neutral": ["了解", "收藏", "学习了", "感谢", "👍"]
        }
        
        # 禁用词列表
        self.banned_words = ["AI", "机器人", "算法", "生成", "自动", "人工智能"]
        
        # 回复历史（用于避免重复）
        self.recent_replies = []
        self.max_history = 20
    
    async def generate_reply(self, post_title: str, post_content: str) -> str:
        """生成短回复"""
        try:
            # 分析内容
            analysis = self.content_analyzer.analyze(post_title, post_content)
            
            # 首先尝试AI生成
            ai_reply = await self._generate_ai_reply(post_title, post_content, analysis)
            
            if ai_reply and self._validate_reply(ai_reply):
                # 检查重复性
                if not self._is_duplicate(ai_reply):
                    self._add_to_history(ai_reply)
                    return ai_reply
            
            # AI生成失败或重复，使用模板回复
            template_reply = self._generate_template_reply(analysis)
            self._add_to_history(template_reply)
            return template_reply
            
        except Exception as e:
            print(f"回复生成失败: {e}")
            # 最终降级方案
            fallback_reply = random.choice(self.reply_templates["通用"]["neutral"])
            self._add_to_history(fallback_reply)
            return fallback_reply
    
    async def _generate_ai_reply(self, title: str, content: str, analysis: ContentAnalysis) -> Optional[str]:
        """使用AI生成回复（带重试机制）"""
        max_retries = 3
        base_delay = 2  # 基础延迟2秒
        
        for attempt in range(max_retries):
            try:
                # 构建简洁的提示词
                prompt = self._build_short_prompt(title, content, analysis)
                
                response = await self.client.chat.completions.create(
                    model=self.config.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "你是一个真实的论坛用户，用简短自然的话回复帖子。"
                        },
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=50,  # 增加token数量以避免截断
                    temperature=self.config.temperature,
                    top_p=0.9
                )
                
                reply = response.choices[0].message.content.strip()
                return self._clean_reply(reply)
                
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "Too Many Requests" in error_str:
                    # API限流，需要等待
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)  # 指数退避
                        print(f"API限流，等待 {delay} 秒后重试... (尝试 {attempt + 1}/{max_retries})")
                        await asyncio.sleep(delay)
                        continue
                    else:
                        print(f"API限流，已达到最大重试次数: {e}")
                        return None
                else:
                    print(f"AI生成失败: {e}")
                    return None
        
        return None
    
    def _build_short_prompt(self, title: str, content: str, analysis: ContentAnalysis) -> str:
        """构建简短提示词（简化版）"""
        # 截取内容，避免过长
        short_content = content[:300] if content else ""
        
        prompt = f"""你是一个活跃的论坛用户，看到这个帖子后想要简短回复：

标题：{title}
内容：{short_content}

请用1-10个字自然回复，就像平时聊天一样。直接给出回复内容："""
        
        return prompt
    
    def _clean_reply(self, reply: str) -> str:
        """清理回复内容"""
        if not reply:
            return ""
            
        # 移除引号和多余符号
        reply = reply.strip('"\'""''')
        
        # 检查并处理编码问题
        try:
            # 确保是有效的UTF-8字符串
            reply = reply.encode('utf-8').decode('utf-8')
        except (UnicodeEncodeError, UnicodeDecodeError):
            # 如果有编码问题，返回默认回复
            return "👍"
        
        # 移除不可见字符和控制字符
        import re
        reply = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', reply)
        
        # 检查是否只包含不可打印字符
        if not reply or not any(c.isprintable() for c in reply):
            return "👍"
        
        # 移除禁用词
        for word in self.banned_words:
            reply = reply.replace(word, "")
        
        # 长度控制
        if len(reply) > self.config.max_length:
            reply = reply[:self.config.max_length]
        
        # 移除多余的标点
        reply = reply.rstrip('。！？，、')
        
        cleaned = reply.strip()
        
        # 如果清理后为空，返回默认回复
        if not cleaned:
            return "👍"
            
        return cleaned
    
    def _validate_reply(self, reply: str) -> bool:
        """验证回复质量"""
        if not reply:
            return False
        
        # 长度检查
        if len(reply) < self.config.min_length or len(reply) > self.config.max_length:
            return False
        
        # 禁用词检查
        for word in self.banned_words:
            if word in reply:
                return False
        
        # 内容质量检查
        if reply.isdigit():  # 纯数字
            return False
        
        if len(set(reply)) == 1:  # 重复字符
            return False
        
        # 检查是否只包含标点符号
        if all(not c.isalnum() for c in reply):
            return False
        
        return True
    
    def _generate_template_reply(self, analysis: ContentAnalysis) -> str:
        """生成模板回复（降级方案）"""
        # 优先使用分类模板
        category = analysis.category
        sentiment = analysis.sentiment
        
        if category in self.reply_templates:
            category_templates = self.reply_templates[category]
            if sentiment in category_templates:
                templates = category_templates[sentiment]
            else:
                # 如果没有对应情感的模板，使用neutral
                templates = category_templates.get("neutral", list(category_templates.values())[0])
        else:
            # 使用通用模板
            universal_templates = self.reply_templates["通用"]
            templates = universal_templates.get(sentiment, universal_templates["neutral"])
        
        # 避免重复
        available_templates = [t for t in templates if not self._is_duplicate(t)]
        if not available_templates:
            available_templates = templates
        
        return random.choice(available_templates)
    
    def _is_duplicate(self, reply: str) -> bool:
        """检查是否与最近回复重复"""
        return reply in self.recent_replies[-10:]  # 检查最近10个回复
    
    def _add_to_history(self, reply: str):
        """添加到回复历史"""
        self.recent_replies.append(reply)
        if len(self.recent_replies) > self.max_history:
            self.recent_replies.pop(0)
    
    def get_reply_statistics(self) -> Dict[str, Any]:
        """获取回复统计信息"""
        if not self.recent_replies:
            return {"total": 0, "unique": 0, "diversity": 0.0}
        
        total = len(self.recent_replies)
        unique = len(set(self.recent_replies))
        diversity = unique / total if total > 0 else 0.0
        
        return {
            "total": total,
            "unique": unique,
            "diversity": diversity,
            "recent_replies": self.recent_replies[-5:]  # 最近5个回复
        }
    
    def clear_history(self):
        """清空回复历史"""
        self.recent_replies.clear()


class SmartReplySelector:
    """智能回复选择器"""
    
    def __init__(self):
        self.reply_history = []
        self.max_history = 50
    
    def select_best_reply(self, candidates: List[str], post_content: str, analysis: ContentAnalysis) -> str:
        """从候选回复中选择最佳回复"""
        if not candidates:
            return "👍"
        
        # 过滤重复回复
        unique_candidates = []
        for reply in candidates:
            if reply not in self.reply_history[-10:]:  # 避免与最近10个回复重复
                unique_candidates.append(reply)
        
        if not unique_candidates:
            unique_candidates = candidates
        
        # 计算相关性得分
        scored_replies = []
        for reply in unique_candidates:
            score = self._calculate_relevance_score(reply, post_content, analysis)
            scored_replies.append((reply, score))
        
        # 选择得分最高的回复
        best_reply = max(scored_replies, key=lambda x: x[1])[0]
        
        # 记录到历史
        self.add_to_history(best_reply)
        
        return best_reply
    
    def _calculate_relevance_score(self, reply: str, post_content: str, analysis: ContentAnalysis) -> float:
        """计算回复相关性得分"""
        score = 0.5  # 基础分数
        
        # 长度适中加分
        if 2 <= len(reply) <= 6:
            score += 0.1
        
        # 包含表情符号加分
        if any(char in reply for char in "👍😊❤️💪🔥"):
            score += 0.1
        
        # 根据分类匹配度加分
        category_matches = {
            "技术讨论": ["学习", "有道理", "赞同", "收藏"],
            "求助问答": ["试试", "有用", "加油", "支持"],
            "生活分享": ["有意思", "赞", "同感", "羡慕"],
            "讨论交流": ["同意", "支持", "认同", "有道理"]
        }
        
        if analysis.category in category_matches:
            category_words = category_matches[analysis.category]
            if any(word in reply for word in category_words):
                score += 0.2
        
        # 根据情感匹配度加分
        if analysis.sentiment == "positive" and any(word in reply for word in ["赞", "好", "棒", "👍"]):
            score += 0.1
        elif analysis.sentiment == "negative" and any(word in reply for word in ["加油", "支持", "理解"]):
            score += 0.1
        
        return min(score, 1.0)
    
    def add_to_history(self, reply: str):
        """添加到回复历史"""
        self.reply_history.append(reply)
        if len(self.reply_history) > self.max_history:
            self.reply_history.pop(0)


class ForumReplyBot:
    """论坛回复机器人"""
    
    def __init__(self, config: ShortReplyConfig):
        self.generator = ShortReplyGenerator(config)
        self.selector = SmartReplySelector()
    
    def generate_reply_for_post(self, post_title: str, post_content: str) -> Tuple[str, ContentAnalysis]:
        """为帖子生成回复"""
        # 分析帖子
        analysis = self.generator.content_analyzer.analyze(post_title, post_content)
        
        # 生成多个候选回复
        candidates = []
        
        # AI生成回复
        ai_reply = self.generator._generate_ai_reply(post_title, post_content, analysis)
        if ai_reply and self.generator._validate_reply(ai_reply):
            candidates.append(ai_reply)
        
        # 模板回复作为备选
        template_reply = self.generator._generate_template_reply(analysis)
        candidates.append(template_reply)
        
        # 选择最佳回复
        best_reply = self.selector.select_best_reply(candidates, post_content, analysis)
        
        return best_reply, analysis
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        generator_stats = self.generator.get_reply_statistics()
        
        return {
            "generator": generator_stats,
            "selector_history_size": len(self.selector.reply_history)
        }


def create_reply_bot_from_config(ai_config: AIConfig) -> ForumReplyBot:
    """从AI配置创建回复机器人"""
    config = ShortReplyConfig(
        api_key=ai_config.api_key,
        base_url=ai_config.base_url,
        model=ai_config.model,
        max_length=10,  # 固定为10字
        min_length=1,   # 固定为1字
        temperature=ai_config.temperature,
        max_tokens=ai_config.max_tokens
    )
    
    return ForumReplyBot(config)


if __name__ == "__main__":
    # 测试短回复生成器
    from ..config.config_manager import ConfigManager
    
    config_manager = ConfigManager()
    ai_config = config_manager.get_ai_config()
    
    # 创建回复机器人
    bot = create_reply_bot_from_config(ai_config)
    
    # 测试回复生成
    test_posts = [
        {
            "title": "Python爬虫问题求助",
            "content": "我在写爬虫的时候遇到了反爬虫机制，有什么好的解决方案吗？"
        },
        {
            "title": "今天天气真好",
            "content": "阳光明媚，心情也变好了，大家今天过得怎么样？"
        },
        {
            "title": "React 19新特性讨论",
            "content": "React 19正式发布，带来了很多新特性，大家怎么看？"
        }
    ]
    
    print("=== 短回复生成测试 ===")
    for i, post in enumerate(test_posts, 1):
        print(f"\n--- 测试帖子 {i} ---")
        print(f"标题: {post['title']}")
        print(f"内容: {post['content']}")
        
        reply, analysis = bot.generate_reply_for_post(post['title'], post['content'])
        print(f"生成回复: {reply}")
        print(f"分析结果: {analysis.category} | {analysis.sentiment} | {analysis.confidence:.2f}")
    
    # 显示统计信息
    print(f"\n=== 统计信息 ===")
    stats = bot.get_statistics()
    print(f"生成器统计: {stats['generator']}")
    print(f"选择器历史: {stats['selector_history_size']}")