"""
内容分析器
分析帖子内容的分类、情感、关键词等
"""

import jieba
import jieba.analyse
import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ContentAnalysis:
    """内容分析结果"""
    category: str
    sentiment: str  # positive, negative, neutral
    keywords: List[str]
    topics: List[str]
    complexity: str  # simple, medium, complex
    intent: str  # question, share, discussion, help
    language_style: str  # formal, casual, technical
    confidence: float


class ContentAnalyzer:
    """内容分析器"""
    
    def __init__(self):
        # 初始化jieba
        jieba.initialize()
        
        # 预定义分类关键词（优化权重）
        self.category_keywords = {
            "求助问答": {
                "high": ["求助", "帮忙", "请教", "救命", "急", "不会", "坏了", "出问题", "故障"],
                "medium": ["问题", "怎么", "如何", "为什么", "错误", "bug", "解决", "修复"],
                "low": ["帮助", "指导", "建议"]
            },
            "技术讨论": {
                "high": ["技术", "代码", "编程", "开发", "算法", "框架"],
                "medium": ["API", "数据库", "服务器", "前端", "后端", "架构"],
                "low": ["实现", "配置", "部署"]
            },
            "生活分享": {
                "high": ["分享", "推荐", "体验", "感受"],
                "medium": ["生活", "日常", "心情"],
                "low": ["今天", "昨天", "最近"]
            },
            "新闻资讯": {
                "high": ["新闻", "资讯", "发布", "更新", "公告"],
                "medium": ["通知", "消息", "报道"],
                "low": ["最新", "官方"]
            },
            "讨论交流": {
                "high": ["讨论", "交流", "观点", "看法"],
                "medium": ["意见", "想法", "认为", "觉得"],
                "low": ["思考", "考虑"]
            },
            "资源分享": {
                "high": ["资源", "下载", "链接", "工具"],
                "medium": ["软件", "教程", "文档", "资料"],
                "low": ["收集", "整理"]
            }
        }
        
        # 情感词典（扩展）
        self.positive_words = ["好", "棒", "赞", "优秀", "完美", "喜欢", "满意", "推荐", "厉害", "不错", "成功", "解决了", "有用", "感谢"]
        self.negative_words = ["差", "烂", "糟糕", "失望", "讨厌", "问题", "错误", "bug", "难用", "垃圾", "坏了", "故障", "不行", "没反应", "出问题", "求助", "救命", "急"]
        
        # 意图识别模式
        self.intent_patterns = {
            "question": [r"[？?]", r"怎么", r"如何", r"为什么", r"什么", r"哪里", r"谁"],
            "help": [r"求助", r"帮忙", r"请教", r"不会", r"救命"],
            "share": [r"分享", r"推荐", r"介绍", r"给大家"],
            "discussion": [r"讨论", r"看法", r"观点", r"意见", r"认为"]
        }
        
        # 技术词汇
        self.tech_words = [
            "Python", "JavaScript", "Java", "C++", "React", "Vue", "Node.js", 
            "Docker", "Kubernetes", "MySQL", "Redis", "MongoDB", "Git", "Linux"
        ]
    
    def analyze(self, title: str, content: str) -> ContentAnalysis:
        """分析内容"""
        full_text = f"{title} {content}"
        
        # 分类识别
        category = self._classify_content(full_text)
        
        # 情感分析
        sentiment = self._analyze_sentiment(full_text)
        
        # 关键词提取
        keywords = self._extract_keywords(full_text)
        
        # 主题提取
        topics = self._extract_topics(full_text)
        
        # 复杂度评估
        complexity = self._assess_complexity(full_text)
        
        # 意图识别
        intent = self._identify_intent(full_text)
        
        # 语言风格
        language_style = self._analyze_language_style(full_text)
        
        # 置信度计算
        confidence = self._calculate_confidence(full_text, category, sentiment)
        
        return ContentAnalysis(
            category=category,
            sentiment=sentiment,
            keywords=keywords,
            topics=topics,
            complexity=complexity,
            intent=intent,
            language_style=language_style,
            confidence=confidence
        )
    
    def _classify_content(self, text: str) -> str:
        """内容分类（使用权重系统）"""
        scores = {}
        text_lower = text.lower()
        
        # 权重设置
        weights = {"high": 3, "medium": 2, "low": 1}
        
        for category, keyword_groups in self.category_keywords.items():
            score = 0
            for weight_level, keywords in keyword_groups.items():
                weight = weights[weight_level]
                for keyword in keywords:
                    count = text_lower.count(keyword.lower())
                    score += count * weight
            scores[category] = score
        
        # 特殊规则：标题中的关键词权重加倍
        title_end = text.find(' ')
        if title_end > 0:
            title = text[:title_end].lower()
            for category, keyword_groups in self.category_keywords.items():
                for weight_level, keywords in keyword_groups.items():
                    weight = weights[weight_level]
                    for keyword in keywords:
                        if keyword.lower() in title:
                            scores[category] += weight * 2
        
        # 返回得分最高的分类
        if scores and max(scores.values()) > 0:
            return max(scores, key=scores.get)
        return "讨论交流"
    
    def _analyze_sentiment(self, text: str) -> str:
        """情感分析"""
        positive_count = sum(text.count(word) for word in self.positive_words)
        negative_count = sum(text.count(word) for word in self.negative_words)
        
        if positive_count > negative_count:
            return "positive"
        elif negative_count > positive_count:
            return "negative"
        else:
            return "neutral"
    
    def _extract_keywords(self, text: str, top_k: int = 5) -> List[str]:
        """提取关键词"""
        try:
            # 使用jieba提取关键词
            keywords = jieba.analyse.extract_tags(text, topK=top_k, withWeight=False)
            return keywords
        except Exception:
            # 简单的关键词提取降级方案
            words = jieba.cut(text)
            word_freq = {}
            for word in words:
                if len(word) > 1 and word not in ['的', '了', '是', '在', '有', '和', '就', '都', '而', '及']:
                    word_freq[word] = word_freq.get(word, 0) + 1
            
            sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
            return [word for word, freq in sorted_words[:top_k]]
    
    def _extract_topics(self, text: str) -> List[str]:
        """提取主题"""
        topics = []
        text_lower = text.lower()
        
        # 技术相关主题
        for topic in self.tech_words:
            if topic.lower() in text_lower:
                topics.append(topic)
        
        # 其他主题识别
        topic_patterns = {
            "前端开发": ["前端", "html", "css", "javascript", "react", "vue"],
            "后端开发": ["后端", "服务器", "数据库", "api", "接口"],
            "移动开发": ["移动", "app", "android", "ios", "flutter"],
            "人工智能": ["ai", "机器学习", "深度学习", "神经网络"],
            "区块链": ["区块链", "比特币", "以太坊", "智能合约"]
        }
        
        for topic, keywords in topic_patterns.items():
            if any(keyword in text_lower for keyword in keywords):
                topics.append(topic)
        
        return topics[:3]  # 最多返回3个主题
    
    def _assess_complexity(self, text: str) -> str:
        """评估内容复杂度"""
        # 基于文本长度和技术词汇密度
        length = len(text)
        tech_count = sum(1 for word in self.tech_words if word.lower() in text.lower())
        
        # 计算技术词汇密度
        tech_density = tech_count / max(length / 100, 1)  # 每100字的技术词汇数
        
        if length > 500 or tech_density > 3:
            return "complex"
        elif length > 200 or tech_density > 1:
            return "medium"
        else:
            return "simple"
    
    def _identify_intent(self, text: str) -> str:
        """识别用户意图"""
        for intent, patterns in self.intent_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text):
                    return intent
        return "discussion"
    
    def _analyze_language_style(self, text: str) -> str:
        """分析语言风格"""
        formal_indicators = ["您", "请", "谢谢", "不好意思", "麻烦", "打扰"]
        casual_indicators = ["哈哈", "嗯", "呀", "啊", "哦", "额"]
        technical_indicators = ["实现", "配置", "部署", "优化", "架构", "算法"]
        
        formal_count = sum(text.count(word) for word in formal_indicators)
        casual_count = sum(text.count(word) for word in casual_indicators)
        technical_count = sum(text.count(word) for word in technical_indicators)
        
        if technical_count > max(formal_count, casual_count):
            return "technical"
        elif formal_count > casual_count:
            return "formal"
        else:
            return "casual"
    
    def _calculate_confidence(self, text: str, category: str, sentiment: str) -> float:
        """计算分析置信度"""
        base_confidence = 0.5
        
        # 文本长度加分
        if len(text) > 50:
            base_confidence += 0.2
        
        # 关键词匹配加分
        if category in self.category_keywords:
            keywords = self.category_keywords[category]
            matches = sum(1 for keyword in keywords if keyword in text.lower())
            base_confidence += min(matches * 0.05, 0.3)
        
        # 情感词匹配加分
        emotion_words = self.positive_words + self.negative_words
        emotion_matches = sum(1 for word in emotion_words if word in text)
        if emotion_matches > 0:
            base_confidence += 0.1
        
        return min(base_confidence, 1.0)
    
    def get_reply_suggestions(self, analysis: ContentAnalysis) -> Dict[str, List[str]]:
        """根据分析结果获取回复建议"""
        suggestions = {
            "short_replies": [],
            "emoji_suggestions": [],
            "tone_suggestions": []
        }
        
        # 根据分类推荐短回复（优化）
        category_replies = {
            "求助问答": ["试试看", "有用", "加油", "支持", "没问题", "可以的", "👍"],
            "技术讨论": ["学习了", "有道理", "赞同", "收藏", "不错", "👍"],
            "生活分享": ["有意思", "赞", "同感", "不错", "😊"],
            "讨论交流": ["同意", "支持", "有道理", "认同", "👍"],
            "新闻资讯": ["关注", "收藏", "有用", "👍"],
            "资源分享": ["感谢", "收藏", "有用", "👍"]
        }
        
        if analysis.category in category_replies:
            suggestions["short_replies"] = category_replies[analysis.category]
        
        # 根据情感推荐表情
        if analysis.sentiment == "positive":
            suggestions["emoji_suggestions"] = ["👍", "😊", "❤️", "🔥", "💪"]
        elif analysis.sentiment == "negative":
            suggestions["emoji_suggestions"] = ["😅", "💪", "🤔"]
        else:
            suggestions["emoji_suggestions"] = ["👍", "🤔", "😊"]
        
        # 根据语言风格推荐语调
        if analysis.language_style == "formal":
            suggestions["tone_suggestions"] = ["感谢分享", "学习了", "受益匪浅"]
        elif analysis.language_style == "casual":
            suggestions["tone_suggestions"] = ["哈哈", "不错", "赞"]
        else:
            suggestions["tone_suggestions"] = ["支持", "同意", "有道理"]
        
        return suggestions


if __name__ == "__main__":
    # 测试内容分析器
    analyzer = ContentAnalyzer()
    
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
    
    for i, post in enumerate(test_posts, 1):
        print(f"\n=== 测试帖子 {i} ===")
        print(f"标题: {post['title']}")
        print(f"内容: {post['content']}")
        
        analysis = analyzer.analyze(post['title'], post['content'])
        print(f"\n分析结果:")
        print(f"  分类: {analysis.category}")
        print(f"  情感: {analysis.sentiment}")
        print(f"  关键词: {analysis.keywords}")
        print(f"  主题: {analysis.topics}")
        print(f"  复杂度: {analysis.complexity}")
        print(f"  意图: {analysis.intent}")
        print(f"  语言风格: {analysis.language_style}")
        print(f"  置信度: {analysis.confidence:.2f}")
        
        suggestions = analyzer.get_reply_suggestions(analysis)
        print(f"\n回复建议:")
        print(f"  短回复: {suggestions['short_replies']}")
        print(f"  表情建议: {suggestions['emoji_suggestions']}")
        print(f"  语调建议: {suggestions['tone_suggestions']}")