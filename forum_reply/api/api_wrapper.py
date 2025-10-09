"""
API接口封装器
提供频率限制、重试机制和错误处理
"""

import time
import random
import asyncio
from typing import Callable, Dict, List, Optional, Tuple, Any
from functools import wraps
from dataclasses import dataclass
from datetime import datetime, timedelta

from .deepflood_client import DeepFloodClient, ForumPost


@dataclass
class APIStats:
    """API统计信息"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    last_request_time: Optional[datetime] = None
    average_response_time: float = 0.0


def async_rate_limit(calls_per_minute: int = 30):
    """异步API调用频率限制装饰器"""
    min_interval = 60.0 / calls_per_minute
    last_called = [0.0]

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            elapsed = time.time() - last_called[0]
            left_to_wait = min_interval - elapsed
            if left_to_wait > 0:
                await asyncio.sleep(left_to_wait)
            ret = await func(*args, **kwargs)
            last_called[0] = time.time()
            return ret
        return wrapper
    return decorator


def async_retry_on_failure(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """异步失败重试装饰器"""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        wait_time = delay * (backoff ** attempt) + random.uniform(0, 1)
                        print(f"第{attempt + 1}次尝试失败: {e}, {wait_time:.2f}秒后重试...")
                        await asyncio.sleep(wait_time)
                    else:
                        print(f"所有重试都失败了: {e}")
            
            raise last_exception
        return wrapper
    return decorator


class APIWrapper:
    """API接口封装器"""
    
    def __init__(self, client: DeepFloodClient, rate_limit_per_minute: int = 20):
        self.client = client
        self.rate_limit_per_minute = rate_limit_per_minute
        self.stats = APIStats()
        self.request_history: List[datetime] = []
        self.max_history_size = 100
    
    def _update_stats(self, success: bool, response_time: float = 0.0):
        """更新统计信息"""
        self.stats.total_requests += 1
        self.stats.last_request_time = datetime.now()
        
        if success:
            self.stats.successful_requests += 1
        else:
            self.stats.failed_requests += 1
        
        # 更新平均响应时间
        if response_time > 0 and self.stats.successful_requests > 0:
            total_successful = self.stats.successful_requests
            current_avg = self.stats.average_response_time
            if total_successful > 0:
                self.stats.average_response_time = (
                    (current_avg * (total_successful - 1) + response_time) / total_successful
                )
        
        # 记录请求历史
        self.request_history.append(datetime.now())
        if len(self.request_history) > self.max_history_size:
            self.request_history.pop(0)
    
    def _check_rate_limit(self) -> bool:
        """检查是否超过频率限制"""
        now = datetime.now()
        one_minute_ago = now - timedelta(minutes=1)
        
        # 统计最近一分钟的请求数
        recent_requests = [
            req_time for req_time in self.request_history 
            if req_time > one_minute_ago
        ]
        
        return len(recent_requests) < self.rate_limit_per_minute
    
    async def _wait_for_rate_limit(self):
        """等待直到可以发送请求"""
        while not self._check_rate_limit():
            wait_time = 60.0 / self.rate_limit_per_minute
            print(f"达到频率限制，等待 {wait_time:.1f} 秒...")
            await asyncio.sleep(wait_time)
    
    @async_rate_limit(calls_per_minute=20)
    @async_retry_on_failure(max_retries=3)
    async def safe_get_post_list(self) -> List[Dict]:
        """安全获取帖子列表"""
        start_time = time.time()
        try:
            await self._wait_for_rate_limit()
            # 在单独的线程中运行同步的阻塞IO操作
            result = await asyncio.to_thread(self.client.get_post_list_from_rss)
            response_time = time.time() - start_time
            self._update_stats(True, response_time)
            return result
        except Exception as e:
            self._update_stats(False)
            raise e
    
    @async_rate_limit(calls_per_minute=15)
    @async_retry_on_failure(max_retries=3)
    async def safe_get_post_detail(self, post_id: int) -> Optional[ForumPost]:
        """安全获取帖子详情"""
        start_time = time.time()
        try:
            await self._wait_for_rate_limit()
            result = await asyncio.to_thread(self.client.get_post_detail, post_id)
            response_time = time.time() - start_time
            self._update_stats(True, response_time)
            return result
        except Exception as e:
            self._update_stats(False)
            raise e
    
    @async_rate_limit(calls_per_minute=10)
    @async_retry_on_failure(max_retries=2)
    async def safe_post_comment(self, post_id: int, content: str) -> Tuple[bool, str]:
        """安全发送回复"""
        start_time = time.time()
        try:
            await self._wait_for_rate_limit()
            result = await asyncio.to_thread(self.client.post_comment, post_id, content)
            response_time = time.time() - start_time
            self._update_stats(result[0], response_time)
            return result
        except Exception as e:
            self._update_stats(False)
            raise e
    
    @async_rate_limit(calls_per_minute=5)
    async def safe_get_categories(self) -> List[Dict]:
        """安全获取分类列表"""
        start_time = time.time()
        try:
            await self._wait_for_rate_limit()
            result = await asyncio.to_thread(self.client.get_categories)
            response_time = time.time() - start_time
            self._update_stats(True, response_time)
            return result
        except Exception as e:
            self._update_stats(False)
            raise e
    
    async def safe_test_connection(self) -> Dict[str, bool]:
        """安全测试连接"""
        try:
            await self._wait_for_rate_limit()
            result = await asyncio.to_thread(self.client.test_connection)
            self._update_stats(result.get('overall', False))
            return result
        except Exception as e:
            self._update_stats(False)
            raise e
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        success_rate = 0.0
        if self.stats.total_requests > 0:
            success_rate = self.stats.successful_requests / self.stats.total_requests
        else:
            success_rate = 0.0
        
        # 计算最近一分钟的请求数
        now = datetime.now()
        one_minute_ago = now - timedelta(minutes=1)
        recent_requests = len([
            req_time for req_time in self.request_history 
            if req_time > one_minute_ago
        ])
        
        return {
            'total_requests': self.stats.total_requests,
            'successful_requests': self.stats.successful_requests,
            'failed_requests': self.stats.failed_requests,
            'success_rate': success_rate,
            'average_response_time': self.stats.average_response_time,
            'last_request_time': self.stats.last_request_time,
            'recent_requests_per_minute': recent_requests,
            'rate_limit_per_minute': self.rate_limit_per_minute
        }
    
    def reset_stats(self):
        """重置统计信息"""
        self.stats = APIStats()
        self.request_history.clear()
    
    def is_healthy(self) -> bool:
        """检查API客户端是否健康"""
        try:
            # 检查最近的成功率
            if self.stats.total_requests >= 10:
                recent_success_rate = self.stats.successful_requests / self.stats.total_requests
                if recent_success_rate < 0.8:  # 成功率低于80%
                    return False
            
            # 检查平均响应时间
            if self.stats.average_response_time > 10.0:  # 响应时间超过10秒
                return False
            
            # 检查最近是否有请求
            if self.stats.last_request_time:
                time_since_last = datetime.now() - self.stats.last_request_time
                if time_since_last > timedelta(minutes=30):  # 30分钟没有请求
                    return False
            
            return True
            
        except Exception:
            return False


class BatchAPIWrapper:
    """批量API操作封装器"""
    
    def __init__(self, api_wrapper: APIWrapper):
        self.api_wrapper = api_wrapper
    
    def batch_get_post_details(self, post_ids: List[int], 
                              batch_size: int = 5, 
                              delay_between_batches: float = 2.0) -> List[Optional[ForumPost]]:
        """批量获取帖子详情"""
        results = []
        
        for i in range(0, len(post_ids), batch_size):
            batch = post_ids[i:i + batch_size]
            batch_results = []
            
            print(f"处理批次 {i//batch_size + 1}/{(len(post_ids) + batch_size - 1)//batch_size}")
            
            for post_id in batch:
                try:
                    detail = self.api_wrapper.safe_get_post_detail(post_id)
                    batch_results.append(detail)
                    
                    # 批次内的小延迟
                    time.sleep(0.5)
                    
                except Exception as e:
                    print(f"获取帖子 {post_id} 详情失败: {e}")
                    batch_results.append(None)
            
            results.extend(batch_results)
            
            # 批次间延迟
            if i + batch_size < len(post_ids):
                time.sleep(delay_between_batches)
        
        return results
    
    def batch_post_comments(self, comments: List[Tuple[int, str]], 
                           batch_size: int = 3,
                           delay_between_batches: float = 5.0) -> List[Tuple[bool, str]]:
        """批量发送回复"""
        results = []
        
        for i in range(0, len(comments), batch_size):
            batch = comments[i:i + batch_size]
            batch_results = []
            
            print(f"发送回复批次 {i//batch_size + 1}/{(len(comments) + batch_size - 1)//batch_size}")
            
            for post_id, content in batch:
                try:
                    result = self.api_wrapper.safe_post_comment(post_id, content)
                    batch_results.append(result)
                    
                    # 回复间的延迟
                    time.sleep(random.uniform(2.0, 5.0))
                    
                except Exception as e:
                    print(f"发送回复到帖子 {post_id} 失败: {e}")
                    batch_results.append((False, str(e)))
            
            results.extend(batch_results)
            
            # 批次间延迟
            if i + batch_size < len(comments):
                time.sleep(delay_between_batches)
        
        return results


if __name__ == "__main__":
    # 测试API封装器
    from ..config.config_manager import ConfigManager
    
    config_manager = ConfigManager()
    forum_config = config_manager.get_forum_config()
    
    client = DeepFloodClient(forum_config)
    api_wrapper = APIWrapper(client, rate_limit_per_minute=20)
    
    # 测试连接
    print("测试连接...")
    try:
        results = api_wrapper.safe_test_connection()
        for key, value in results.items():
            print(f"  {key}: {'✓' if value else '✗'}")
    except Exception as e:
        print(f"连接测试失败: {e}")
    
    # 获取统计信息
    print("\nAPI统计信息:")
    stats = api_wrapper.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    # 测试健康检查
    print(f"\nAPI健康状态: {'健康' if api_wrapper.is_healthy() else '不健康'}")