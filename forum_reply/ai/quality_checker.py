"""
回复质量检查器
检查回复的质量、相关性和安全性
"""

import jieba
import re
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from datetime import datetime

from .content_analyzer import ContentAnalysis


@dataclass
class QualityScore:
    """质量评分结果"""
    total_score: float
    component_scores: Dict[str, float]
    pass_threshold: bool
    feedback: List[str]


class QualityChecker:
    """回复质量检查器"""
    
    def __init__(self):
        # 违禁词列表
        self.banned_words = [
            "广告", "推广", "加微信", "QQ群", "刷单", "代刷",
            "AI", "机器人", "算法", "生成", "自动", "人工智能"
        ]
        
        # 低质量模式
        self.low_quality_patterns = [
            r"^[.。]+$",  # 只有标点
            r"^[0-9]+$",  # 只有数字
            r"^(.)\1{2,}$",  # 重复字符
            r"^[a-zA-Z]+$",  # 只有英文字母
        ]
        
        # 积极词汇
        self.positive_words = [
            "赞", "好", "棒", "支持", "不错", "厉害", "学习", "收藏",
            "感谢", "有用", "有道理", "同意", "认同", "确实"
        ]
        
        # 自然表达模式
        self.natural_patterns = [
            "👍", "😊", "❤️", "💪", "🔥",  # 表情符号
            "哈哈", "嗯", "呀", "啊", "哦",  # 语气词
            "学习了", "收藏了", "试试看", "可以的", "没问题"  # 自然表达
        ]
    
    def check_quality(self, reply: str, post_title: str, post_content: str, 
                     analysis: ContentAnalysis) -> QualityScore:
        """检查回复质量"""
        scores = {}
        feedback = []
        
        # 1. 长度适中性检查 (0-1)
        length_score, length_feedback = self._check_length(reply)
        scores['length'] = length_score
        if length_feedback:
            feedback.append(length_feedback)
        
        # 2. 相关性检查 (0-1)
        relevance_score, relevance_feedback = self._check_relevance(reply, post_title, post_content)
        scores['relevance'] = relevance_score
        if relevance_feedback:
            feedback.append(relevance_feedback)
        
        # 3. 自然度检查 (0-1)
        naturalness_score, naturalness_feedback = self._check_naturalness(reply)
        scores['naturalness'] = naturalness_score
        if naturalness_feedback:
            feedback.append(naturalness_feedback)
        
        # 4. 安全性检查 (0-1)
        safety_score, safety_feedback = self._check_safety(reply)
        scores['safety'] = safety_score
        if safety_feedback:
            feedback.append(safety_feedback)
        
        # 5. 表达效果检查 (0-1)
        expression_score, expression_feedback = self._check_expression(reply, analysis)
        scores['expression'] = expression_score
        if expression_feedback:
            feedback.append(expression_feedback)
        
        # 计算综合得分（短回复权重调整）
        weights = {
            'length': 0.25,      # 长度很重要
            'relevance': 0.20,   # 相关性重要
            'naturalness': 0.30, # 自然度最重要
            'safety': 0.15,      # 安全性
            'expression': 0.10   # 表达效果
        }
        
        total_score = sum(scores[key] * weights[key] for key in scores)
        pass_threshold = total_score >= 0.6  # 短回复阈值稍低
        
        return QualityScore(
            total_score=total_score,
            component_scores=scores,
            pass_threshold=pass_threshold,
            feedback=feedback
        )
    
    def _check_length(self, reply: str) -> Tuple[float, Optional[str]]:
        """检查长度适中性"""
        length = len(reply)
        
        if 1 <= length <= 10:
            return 1.0, None
        elif length == 0:
            return 0.0, "回复为空"
        elif length > 10:
            return max(0, 1 - (length - 10) * 0.1), f"回复过长({length}字)"
        else:
            return 0.0, "回复长度异常"
    
    def _check_relevance(self, reply: str, post_title: str, post_content: str) -> Tuple[float, Optional[str]]:
        """检查相关性"""
        try:
            # 提取帖子和回复的关键词
            post_text = f"{post_title} {post_content}"
            post_words = set(jieba.cut(post_text.lower()))
            reply_words = set(jieba.cut(reply.lower()))
            
            # 移除停用词
            stop_words = {'的', '了', '是', '在', '有', '和', '就', '都', '而', '及', '与', '或'}
            post_words = post_words - stop_words
            reply_words = reply_words - stop_words
            
            if not post_words or not reply_words:
                # 如果无法提取关键词，检查是否是通用积极回复
                if any(word in reply for word in self.positive_words):
                    return 0.7, None
                return 0.5, None
            
            # 计算关键词重叠度
            overlap = post_words.intersection(reply_words)
            relevance = len(overlap) / max(len(post_words), len(reply_words))
            
            # 对于短回复，降低相关性要求
            if len(reply) <= 5:
                relevance = max(relevance, 0.6)  # 短回复给予基础相关性
            
            if relevance < 0.3:
                return relevance, "回复与帖子内容相关性较低"
            
            return relevance, None
            
        except Exception:
            # 降级检查：是否包含积极词汇
            if any(word in reply for word in self.positive_words):
                return 0.7, None
            return 0.5, None
    
    def _check_naturalness(self, reply: str) -> Tuple[float, Optional[str]]:
        """检查自然度"""
        score = 0.5  # 基础分数
        
        # 检查低质量模式
        for pattern in self.low_quality_patterns:
            if re.match(pattern, reply):
                return 0.1, "回复模式不自然"
        
        # 检查是否包含自然表达
        natural_count = sum(1 for pattern in self.natural_patterns if pattern in reply)
        if natural_count > 0:
            score += 0.3
        
        # 检查是否包含积极词汇
        positive_count = sum(1 for word in self.positive_words if word in reply)
        if positive_count > 0:
            score += 0.2
        
        # 长度适中加分
        if 2 <= len(reply) <= 8:
            score += 0.1
        
        # 检查字符多样性
        if len(set(reply)) > 1:
            score += 0.1
        
        return min(score, 1.0), None
    
    def _check_safety(self, reply: str) -> Tuple[float, Optional[str]]:
        """检查安全性"""
        # 检查违禁词
        for word in self.banned_words:
            if word in reply:
                return 0.0, f"包含违禁词: {word}"
        
        # 检查是否包含敏感内容
        sensitive_patterns = [
            r"微信", r"QQ", r"群", r"加我", r"联系",
            r"广告", r"推广", r"营销", r"代理"
        ]
        
        for pattern in sensitive_patterns:
            if re.search(pattern, reply):
                return 0.3, f"可能包含敏感内容: {pattern}"
        
        return 1.0, None
    
    def _check_expression(self, reply: str, analysis: ContentAnalysis) -> Tuple[float, Optional[str]]:
        """检查表达效果"""
        score = 0.5  # 基础分数
        
        # 表情符号加分
        emoji_count = sum(1 for char in reply if char in "👍😊❤️💪🔥🤔😅")
        if emoji_count > 0:
            score += 0.3
        
        # 根据帖子分类检查表达适配性
        category_expressions = {
            "技术讨论": ["学习", "有道理", "赞同", "收藏", "👍"],
            "求助问答": ["试试", "有用", "加油", "支持", "可以"],
            "生活分享": ["有意思", "赞", "同感", "羡慕", "😊"],
            "讨论交流": ["同意", "支持", "认同", "有道理", "👍"]
        }
        
        if analysis.category in category_expressions:
            expressions = category_expressions[analysis.category]
            if any(expr in reply for expr in expressions):
                score += 0.2
        
        # 情感匹配检查
        if analysis.sentiment == "positive" and any(word in reply for word in ["赞", "好", "棒", "👍"]):
            score += 0.1
        elif analysis.sentiment == "negative" and any(word in reply for word in ["加油", "支持", "理解"]):
            score += 0.1
        
        return min(score, 1.0), None
    
    def batch_check_quality(self, replies: List[Tuple[str, str, str, ContentAnalysis]]) -> List[QualityScore]:
        """批量检查回复质量"""
        results = []
        
        for reply, post_title, post_content, analysis in replies:
            quality_score = self.check_quality(reply, post_title, post_content, analysis)
            results.append(quality_score)
        
        return results
    
    def get_quality_statistics(self, quality_scores: List[QualityScore]) -> Dict[str, Any]:
        """获取质量统计信息"""
        if not quality_scores:
            return {}
        
        total_count = len(quality_scores)
        passed_count = sum(1 for score in quality_scores if score.pass_threshold)
        
        # 计算各项平均分
        avg_scores = {}
        for component in ['length', 'relevance', 'naturalness', 'safety', 'expression']:
            avg_scores[component] = sum(
                score.component_scores.get(component, 0) for score in quality_scores
            ) / total_count
        
        avg_total = sum(score.total_score for score in quality_scores) / total_count
        
        return {
            'total_count': total_count,
            'passed_count': passed_count,
            'pass_rate': passed_count / total_count,
            'average_total_score': avg_total,
            'average_component_scores': avg_scores,
            'quality_distribution': {
                'excellent': sum(1 for s in quality_scores if s.total_score >= 0.8),
                'good': sum(1 for s in quality_scores if 0.6 <= s.total_score < 0.8),
                'poor': sum(1 for s in quality_scores if s.total_score < 0.6)
            }
        }


class AdaptiveQualityChecker(QualityChecker):
    """自适应质量检查器"""
    
    def __init__(self):
        super().__init__()
        self.quality_history = []
        self.max_history = 100
        self.threshold_adjustment = 0.0
    
    def check_quality_adaptive(self, reply: str, post_title: str, post_content: str, 
                              analysis: ContentAnalysis) -> QualityScore:
        """自适应质量检查"""
        # 基础质量检查
        quality_score = self.check_quality(reply, post_title, post_content, analysis)
        
        # 记录历史
        self.quality_history.append(quality_score.total_score)
        if len(self.quality_history) > self.max_history:
            self.quality_history.pop(0)
        
        # 自适应调整阈值
        self._adjust_threshold()
        
        # 重新计算是否通过
        adjusted_threshold = 0.6 + self.threshold_adjustment
        quality_score.pass_threshold = quality_score.total_score >= adjusted_threshold
        
        return quality_score
    
    def _adjust_threshold(self):
        """根据历史质量调整阈值"""
        if len(self.quality_history) < 10:
            return
        
        recent_avg = sum(self.quality_history[-10:]) / 10
        overall_avg = sum(self.quality_history) / len(self.quality_history)
        
        # 如果最近质量下降，降低阈值
        if recent_avg < overall_avg - 0.1:
            self.threshold_adjustment = max(self.threshold_adjustment - 0.05, -0.2)
        # 如果最近质量提升，提高阈值
        elif recent_avg > overall_avg + 0.1:
            self.threshold_adjustment = min(self.threshold_adjustment + 0.05, 0.2)
    
    def get_adaptive_stats(self) -> Dict[str, Any]:
        """获取自适应统计信息"""
        if not self.quality_history:
            return {}
        
        return {
            'history_count': len(self.quality_history),
            'recent_average': sum(self.quality_history[-10:]) / min(10, len(self.quality_history)),
            'overall_average': sum(self.quality_history) / len(self.quality_history),
            'threshold_adjustment': self.threshold_adjustment,
            'current_threshold': 0.6 + self.threshold_adjustment
        }


if __name__ == "__main__":
    # 测试质量检查器
    from .content_analyzer import ContentAnalyzer
    
    analyzer = ContentAnalyzer()
    checker = QualityChecker()
    
    # 测试数据
    test_cases = [
        {
            "reply": "👍",
            "title": "Python学习心得",
            "content": "最近在学Python，感觉很有意思"
        },
        {
            "reply": "学习了",
            "title": "React新特性介绍",
            "content": "React 19带来了很多新功能"
        },
        {
            "reply": "广告推广加微信",
            "title": "技术讨论",
            "content": "讨论一下新技术"
        },
        {
            "reply": "aaaaaaa",
            "title": "求助帖",
            "content": "遇到了问题"
        },
        {
            "reply": "有道理，支持",
            "title": "观点分享",
            "content": "我觉得这个想法很好"
        }
    ]
    
    print("=== 质量检查测试 ===")
    for i, case in enumerate(test_cases, 1):
        print(f"\n--- 测试案例 {i} ---")
        print(f"回复: {case['reply']}")
        print(f"帖子: {case['title']}")
        
        # 分析帖子内容
        analysis = analyzer.analyze(case['title'], case['content'])
        
        # 检查质量
        quality = checker.check_quality(
            case['reply'], case['title'], case['content'], analysis
        )
        
        print(f"总分: {quality.total_score:.2f}")
        print(f"通过: {'✓' if quality.pass_threshold else '✗'}")
        print(f"各项得分: {quality.component_scores}")
        if quality.feedback:
            print(f"反馈: {quality.feedback}")
    
    # 测试自适应检查器
    print(f"\n=== 自适应质量检查测试 ===")
    adaptive_checker = AdaptiveQualityChecker()
    
    for case in test_cases:
        analysis = analyzer.analyze(case['title'], case['content'])
        quality = adaptive_checker.check_quality_adaptive(
            case['reply'], case['title'], case['content'], analysis
        )
        print(f"回复: {case['reply']} | 得分: {quality.total_score:.2f} | 通过: {'✓' if quality.pass_threshold else '✗'}")
    
    print(f"\n自适应统计: {adaptive_checker.get_adaptive_stats()}")