"""
DeepFlood论坛API客户端
支持帖子获取、回复发送等功能
"""

import requests
from curl_cffi import requests as cffi_requests
import hashlib
import hmac
import time
import json
import os
import re
import random
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from dataclasses import dataclass
from datetime import datetime
import xml.etree.ElementTree as ET

# Selenium and browser automation imports
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from urllib.parse import urlparse


from ..config.config_manager import ForumConfig


@dataclass
class ForumPost:
    """论坛帖子数据结构"""
    post_id: int
    title: str
    content: str
    author: str
    author_id: int
    category: str
    created_time: datetime
    reply_count: int
    view_count: int
    url: str


@dataclass
class ForumComment:
    """论坛评论数据结构"""
    comment_id: int
    post_id: int
    content: str
    author: str
    author_id: int
    created_time: datetime
    parent_id: Optional[int] = None


class DeepFloodClient:
    """DeepFlood论坛API客户端"""
    
    def __init__(self, config: ForumConfig):
        self.config = config
        # 使用 curl_cffi 创建会话，模拟浏览器指纹
        self.session = cffi_requests.Session(
            impersonate="chrome110",
            timeout=self.config.request_timeout
        )
        self.session_cookie = config.session_cookie
        
        # 解析cookie并立即设置到会话中
        self.cookies = self._parse_cookie(config.session_cookie)
        self.session.cookies.update(self.cookies)
        
        # 设置基础请求头
        self._setup_headers()
        
        # 初始化认证信息
        # self._init_auth_info() # 禁用旧的认证逻辑
    
    def _parse_cookie(self, cookie_str: str) -> Dict[str, str]:
        """解析cookie字符串"""
        cookies = {}
        if not cookie_str:
            return cookies
            
        for item in cookie_str.split(';'):
            if '=' in item:
                key, value = item.strip().split('=', 1)
                cookies[key] = value
        return cookies
    
    def _setup_headers(self):
        """设置基础请求头（参照nodeseek_sign.py）"""
        self.session.headers.update({
            'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
            # 'Cookie': self.session_cookie, # cffi_requests 会自动管理cookie
            'origin': self.config.base_url,
            'referer': f'{self.config.base_url}/board',
            'Content-Type': 'application/json'
        })
        
        # 设置超时
        # cffi_requests.Session 在初始化时已设置超时
    
    def _setup_driver(self):
        """
        初始化undetected_chromedriver并设置cookie
        参照 nodeseek_daily.py 的实现
        """
        try:
            print("开始初始化浏览器 (undetected_chromedriver)...")
            options = uc.ChromeOptions()
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            
            # 默认使用无头模式
            options.add_argument('--headless')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size=1920,1080')
            options.add_argument(f'--user-agent={self.session.headers["User-Agent"]}')
            
            # 从环境变量中获取驱动路径和版本号
            driver_executable_path = os.getenv('DRIVER_EXECUTABLE_PATH')
            chrome_version_str = os.getenv('CHROME_VERSION')

            kwargs = {'options': options}

            # 如果在Dockerfile中设置了驱动路径，则使用它
            if driver_executable_path:
                print(f"使用系统提供的驱动: {driver_executable_path}")
                kwargs['executable_path'] = driver_executable_path
            
            # 如果在Dockerfile中设置了版本号，则使用它
            if chrome_version_str and chrome_version_str.isdigit():
                print(f"使用指定的主版本号: {chrome_version_str}")
                kwargs['version_main'] = int(chrome_version_str)
            else:
                print("在Docker环境中运行，自动检测Chrome版本...")
            
            driver = uc.Chrome(**kwargs)
            # 解决在程序退出时可能出现的 "句柄无效" 错误
            # 通过将__del__设置为空操作，防止驱动在垃圾回收时再次尝试退出
            driver.__del__ = lambda: None
            
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            print("浏览器启动成功，正在设置cookie...")
            driver.get(self.config.base_url)
            time.sleep(2)

            hostname = urlparse(self.config.base_url).hostname
            cookie_domain = '.' + '.'.join(hostname.split('.')[-2:]) if hostname else ""
            
            for name, value in self.cookies.items():
                driver.add_cookie({
                    'name': name,
                    'value': value,
                    'domain': cookie_domain,
                    'path': '/'
                })
            
            print("刷新页面以应用cookie...")
            driver.refresh()
            time.sleep(3)
            
            return driver
            
        except Exception as e:
            print(f"设置浏览器和Cookie时出错: {e}")
            import traceback
            traceback.print_exc()
            return None

    # _init_auth_info, _generate_refract_sign, _get_csrf_token 已被移除或禁用
    # 新逻辑集成在 post_comment 中
    
    def get_post_list_from_rss(self) -> List[Dict]:
        """从RSS获取帖子列表"""
        try:
            # 使用feed.deepflood.com的RSS地址
            rss_url = "https://feed.deepflood.com/topic.rss.xml"
            
            # 设置特殊的请求头
            headers = {
                'User-Agent': self.config.user_agent,
                'Accept': 'application/rss+xml, application/xml, text/xml',
                'Accept-Language': 'zh-CN,zh;q=0.9',
                'Cache-Control': 'no-cache'
            }
            
            response = requests.get(rss_url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                return self._parse_rss_feed(response.text)
            else:
                print(f"获取RSS失败: {response.status_code}")
                print(f"响应内容: {response.text[:200]}")
                return []
                
        except Exception as e:
            print(f"获取RSS异常: {e}")
            return []
    
    def _parse_rss_feed(self, rss_content: str) -> List[Dict]:
        """解析RSS内容"""
        posts = []
        try:
            root = ET.fromstring(rss_content)
            
            for item in root.findall('.//item'):
                title_elem = item.find('title')
                link_elem = item.find('link')
                description_elem = item.find('description')
                pub_date_elem = item.find('pubDate')
                
                if title_elem is not None and link_elem is not None:
                    post_id = self._extract_post_id_from_url(link_elem.text)
                    
                    if post_id:
                        post = {
                            'post_id': post_id,
                            'title': title_elem.text or '',
                            'description': description_elem.text or '' if description_elem is not None else '',
                            'url': link_elem.text,
                            'pub_date': pub_date_elem.text or '' if pub_date_elem is not None else ''
                        }
                        posts.append(post)
                        
        except Exception as e:
            print(f"解析RSS失败: {e}")
            
        return posts
    
    def _extract_post_id_from_url(self, url: str) -> Optional[int]:
        """从URL中提取帖子ID"""
        match = re.search(r'/post-(\d+)-', url)
        return int(match.group(1)) if match else None
    
    def get_post_detail(self, post_id: int) -> Optional[ForumPost]:
        """获取帖子详情"""
        try:
            url = f"{self.config.base_url}/post-{post_id}-1"
            
            # 更新referer
            headers = self.session.headers.copy()
            headers['referer'] = url
            
            response = self.session.get(url, headers=headers)
            
            if response.status_code == 200:
                return self._parse_post_detail(response.text, post_id, url)
            else:
                # 【重要修改】打印详细的失败状态码
                print(f"获取帖子 {post_id} 详情失败, HTTP 状态码: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"获取帖子 {post_id} 详情时发生网络异常: {e}")
            return None
    
    def _parse_post_detail(self, html_content: str, post_id: int, url: str) -> Optional[ForumPost]:
        """解析帖子详情页面"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 提取标题
            title = ""
            title_selectors = ['h1', '.post-title', '.title', '[data-title]']
            for selector in title_selectors:
                title_elem = soup.select_one(selector)
                if title_elem:
                    title = title_elem.get_text().strip()
                    break
            
            # 提取内容
            content = ""
            content_selectors = ['.post-content', '.content', '.post-body', '[data-content]']
            for selector in content_selectors:
                content_elem = soup.select_one(selector)
                if content_elem:
                    content = content_elem.get_text().strip()
                    break
            
            # 提取作者信息
            author = ""
            author_id = 0
            author_selectors = ['.author', '.username', '.user-name', '[data-author]']
            for selector in author_selectors:
                author_elem = soup.select_one(selector)
                if author_elem:
                    author = author_elem.get_text().strip()
                    # 尝试提取作者ID
                    author_link = author_elem.find('a') or author_elem
                    if author_link and author_link.get('href'):
                        author_id_match = re.search(r'/user/(\d+)', author_link.get('href'))
                        if author_id_match:
                            author_id = int(author_id_match.group(1))
                    break
            
            # 提取其他元数据
            reply_count = 0
            view_count = 0
            meta_info = soup.select('.meta, .post-meta, .info')
            for meta in meta_info:
                text = meta.get_text()
                
                # 提取回复数
                reply_match = re.search(r'(\d+)\s*回复', text)
                if reply_match:
                    reply_count = int(reply_match.group(1))
                
                # 提取浏览数
                view_match = re.search(r'(\d+)\s*浏览', text)
                if view_match:
                    view_count = int(view_match.group(1))
            
            return ForumPost(
                post_id=post_id,
                title=title,
                content=content,
                author=author,
                author_id=author_id,
                category="",  # 需要进一步解析
                created_time=datetime.now(),  # 需要进一步解析
                reply_count=reply_count,
                view_count=view_count,
                url=url
            )
            
        except Exception as e:
            print(f"解析帖子详情失败: {e}")
            return None
    
    def post_comment(self, post_id: int, content: str) -> Tuple[bool, str]:
        """
        发送回复，使用Selenium模拟浏览器操作
        参照 nodeseek_daily.py 的实现
        """
        driver = self._setup_driver()
        if not driver:
            return False, "浏览器驱动初始化失败。"

        try:
            post_url = f'{self.config.base_url}/post-{post_id}-1'
            print(f"正在使用Selenium访问帖子: {post_url}")
            driver.get(post_url)

            # 等待 CodeMirror 编辑器加载
            print("等待评论框加载...")
            editor = WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '.CodeMirror'))
            )
            
            # 点击编辑器区域获取焦点
            editor.click()
            time.sleep(0.5)
            print("评论框已聚焦，准备输入内容...")

            # 模拟输入
            actions = ActionChains(driver)
            for char in content:
                actions.send_keys(char)
                actions.pause(random.uniform(0.1, 0.3))
            actions.perform()
            
            print("内容输入完成，准备提交...")
            time.sleep(2)
            
            # 使用更精确的选择器定位提交按钮
            submit_button = WebDriverWait(driver, 30).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'submit') and contains(text(), '发布评论')]"))
            )
            # 确保按钮可见并可点击
            driver.execute_script("arguments[0].scrollIntoView(true);", submit_button)
            time.sleep(0.5)
            submit_button.click()
            
            print(f"评论已在帖子 {post_url} 中提交")
            
            # 等待几秒钟，让提交完成，也可以在这里加入检查评论是否成功的逻辑
            time.sleep(3)
            
            return True, "评论已通过浏览器模拟成功提交"

        except Exception as e:
            print(f"使用Selenium评论时出错: {e}")
            # 可以在这里增加错误调试信息，例如截图
            # driver.save_screenshot(f'error_comment_{post_id}.png')
            # with open(f'error_comment_{post_id}.html', 'w', encoding='utf-8') as f:
            #     f.write(driver.page_source)
            import traceback
            traceback.print_exc()
            return False, f"使用Selenium评论时出错: {e}"
        finally:
            if driver:
                print("关闭浏览器驱动...")
                try:
                    driver.quit()
                except Exception as e:
                    print(f"关闭浏览器驱动时出错 (可忽略): {e}")
                
    
    def get_categories(self) -> List[Dict]:
        """获取分类列表"""
        try:
            url = f"{self.config.base_url}/api/content/list-categories"
            
            # 准备请求头
            headers = self.session.headers.copy()
            headers.update({
                'Content-Type': 'application/json',
                'Content-Length': '0',
                'origin': self.config.base_url,
                # 'refract-sign': self._generate_refract_sign('/api/content/list-categories', 'POST') # 禁用
            })
            
            response = self.session.post(url, headers=headers)
            
            if response.status_code == 200:
                return response.json().get('data', [])
            else:
                print(f"获取分类列表失败: {response.status_code}")
                return []
                
        except Exception as e:
            print(f"获取分类列表异常: {e}")
            return []
    
    def get_account_info(self, user_id: int) -> Optional[Dict]:
        """获取用户信息"""
        try:
            url = f"{self.config.base_url}/api/account/getInfo/{user_id}"
            
            headers = self.session.headers.copy()
            headers.update({
                'Content-Type': 'application/json',
                # 'refract-sign': self._generate_refract_sign(f'/api/account/getInfo/{user_id}') # 禁用
            })
            
            response = self.session.get(url, headers=headers)
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"获取用户信息失败: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"获取用户信息异常: {e}")
            return None
    
    def get_unread_notifications(self) -> Optional[Dict]:
        """获取未读通知数量"""
        try:
            url = f"{self.config.base_url}/api/notification/unread-count"
            
            headers = self.session.headers.copy()
            # headers['refract-sign'] = self._generate_refract_sign('/api/notification/unread-count') # 禁用
            
            response = self.session.get(url, headers=headers)
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"获取通知失败: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"获取通知异常: {e}")
            return None
    
    def ping(self) -> bool:
        """心跳检测"""
        try:
            url = f"{self.config.base_url}/edge-cgi/ping"
            
            headers = self.session.headers.copy()
            # headers['refract-sign'] = self._generate_refract_sign('/edge-cgi/ping') # 禁用
            
            response = self.session.get(url, headers=headers)
            return response.status_code == 200
            
        except Exception as e:
            print(f"心跳检测异常: {e}")
            return False
    
    def test_connection(self) -> Dict[str, bool]:
        """测试连接状态"""
        results = {
            'ping': False,
            'get_categories': False,
            'get_notifications': False,
            'overall': False
        }
        
        try:
            # 测试心跳
            results['ping'] = self.ping()
            
            # 测试获取分类
            categories = self.get_categories()
            results['get_categories'] = len(categories) > 0
            
            # 测试获取通知
            notifications = self.get_unread_notifications()
            results['get_notifications'] = notifications is not None
            
            # 整体状态
            results['overall'] = all([results['ping'], results['get_categories']])
            
        except Exception as e:
            print(f"连接测试异常: {e}")
        
        return results


if __name__ == "__main__":
    # 测试客户端
    from ..config.config_manager import ConfigManager
    
    config_manager = ConfigManager()
    forum_config = config_manager.get_forum_config()
    
    client = DeepFloodClient(forum_config)
    
    # 测试连接
    print("测试连接...")
    results = client.test_connection()
    for key, value in results.items():
        print(f"  {key}: {'✓' if value else '✗'}")
    
    # 测试获取帖子列表
    print("\n获取帖子列表...")
    posts = client.get_post_list_from_rss()
    print(f"获取到 {len(posts)} 个帖子")
    
    if posts:
        # 测试获取帖子详情
        first_post = posts[0]
        print(f"\n获取帖子详情: {first_post['title']}")
        detail = client.get_post_detail(first_post['post_id'])
        if detail:
            print(f"  标题: {detail.title}")
            print(f"  作者: {detail.author}")
            print(f"  内容长度: {len(detail.content)}")
