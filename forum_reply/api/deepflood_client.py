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
        self.session = cffi_requests.Session(impersonate="chrome110", timeout=self.config.request_timeout)
        self.session_cookie = config.session_cookie
        self.cookies = self._parse_cookie(config.session_cookie)
        self.session.cookies.update(self.cookies)
        self._setup_headers()
    
    def _parse_cookie(self, cookie_str: str) -> Dict[str, str]:
        cookies = {}
        if not cookie_str: return cookies
        for item in cookie_str.split(';'):
            if '=' in item:
                key, value = item.strip().split('=', 1)
                cookies[key] = value
        return cookies
    
    def _setup_headers(self):
        self.session.headers.update({
            'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0"
        })

    def _save_cookies_from_driver(self, driver):
        """【新增】从浏览器实例获取最新Cookie并保存到持久化文件"""
        try:
            # 1. 从浏览器获取所有当前域的Cookie
            current_cookies = driver.get_cookies()
            if not current_cookies:
                print("警告: 未能从浏览器中获取到任何Cookie。")
                return

            # 2. 将Cookie列表转换为标准的字符串格式
            new_cookie_string = "; ".join([f"{c['name']}={c['value']}" for c in current_cookies])

            # 3. 只有当Cookie发生变化时才写入文件，避免不必要的操作
            if new_cookie_string and new_cookie_string != self.session_cookie:
                cookie_file = self.config.cookie_file_path
                cookie_data = {
                    "cookie_string": new_cookie_string,
                    "updated_at": datetime.now().isoformat()
                }
                
                # 确保目录存在
                os.makedirs(os.path.dirname(cookie_file), exist_ok=True)
                
                with open(cookie_file, 'w', encoding='utf-8') as f:
                    json.dump(cookie_data, f, ensure_ascii=False, indent=2)
                
                print(f"检测到Cookie更新，已将最新Cookie保存到 {cookie_file}")
                # 更新当前实例的cookie，确保本次运行的后续操作也使用新cookie
                self.session_cookie = new_cookie_string
            else:
                print("Cookie未发生变化，无需更新。")

        except Exception as e:
            print(f"保存最新Cookie时发生错误: {e}")

    def _setup_driver(self):
        try:
            print("开始初始化浏览器 (undetected_chromedriver)...")
            options = uc.ChromeOptions()
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--headless')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size=1920,1080')
            options.add_argument(f'--user-agent={self.session.headers["User-Agent"]}')
            options.add_argument('--lang=zh-CN,zh')
            options.add_argument('--disable-infobars')
            
            driver_executable_path = os.getenv('DRIVER_EXECUTABLE_PATH')
            chrome_version_str = os.getenv('CHROME_VERSION')
            kwargs = {'options': options}
            if driver_executable_path: kwargs['executable_path'] = driver_executable_path
            if chrome_version_str and chrome_version_str.isdigit(): kwargs['version_main'] = int(chrome_version_str)
            
            driver = uc.Chrome(**kwargs)
            driver.__del__ = lambda: None
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            print("浏览器启动成功，正在设置cookie...")
            driver.get(self.config.base_url)
            time.sleep(2)

            hostname = urlparse(self.config.base_url).hostname
            cookie_domain = '.' + '.'.join(hostname.split('.')[-2:]) if hostname else ""
            
            # 使用初始化的Cookie（来自文件或环境变量）
            for name, value in self.cookies.items():
                driver.add_cookie({'name': name, 'value': value, 'domain': cookie_domain, 'path': '/'})
            
            # 刷新页面以应用Cookie并可能获得服务器更新的Cookie
            driver.refresh()
            print("页面刷新完成，等待加载...")
            time.sleep(3)

            # 【重要修改】在成功加载后，调用保存Cookie的函数
            self._save_cookies_from_driver(driver)
            
            return driver
        except Exception as e:
            print(f"设置浏览器和Cookie时出错: {e}")
            import traceback
            traceback.print_exc()
            return None

    # (省略了 get_post_list_from_rss, _parse_rss_feed, _extract_post_id_from_url 等函数的完整代码，它们未被修改)
    def get_post_list_from_rss(self) -> List[Dict]:
        try:
            rss_url = "https://feed.deepflood.com/topic.rss.xml"
            headers = {'User-Agent': self.config.user_agent, 'Accept': 'application/rss+xml, application/xml, text/xml', 'Cache-Control': 'no-cache'}
            response = requests.get(rss_url, headers=headers, timeout=30)
            if response.status_code == 200: return self._parse_rss_feed(response.text)
            else:
                print(f"获取RSS失败: {response.status_code}")
                return []
        except Exception as e:
            print(f"获取RSS异常: {e}")
            return []
    def _parse_rss_feed(self, rss_content: str) -> List[Dict]:
        posts = []
        try:
            root = ET.fromstring(rss_content)
            for item in root.findall('.//item'):
                title_elem, link_elem = item.find('title'), item.find('link')
                if title_elem is not None and link_elem is not None:
                    post_id = self._extract_post_id_from_url(link_elem.text)
                    if post_id: posts.append({'post_id': post_id, 'title': title_elem.text or '', 'url': link_elem.text})
        except Exception as e:
            print(f"解析RSS失败: {e}")
        return posts
    def _extract_post_id_from_url(self, url: str) -> Optional[int]:
        match = re.search(r'/post-(\d+)-', url)
        return int(match.group(1)) if match else None

    def get_post_detail(self, post_id: int) -> Optional[ForumPost]:
        driver = None
        try:
            url = f"{self.config.base_url}/post-{post_id}-1"
            print(f"正在使用浏览器环境获取帖子 {post_id} 详情...")
            driver = self._setup_driver()
            if not driver:
                print(f"为帖子 {post_id} 初始化浏览器失败。")
                return None
            driver.get(url)
            print(f"等待帖子 {post_id} 正文加载...")
            WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'article.post-content')))
            time.sleep(random.uniform(1.5, 2.5))
            html_content = driver.page_source
            if "帖子不存在" in html_content or "not found" in html_content.lower():
                print(f"获取帖子 {post_id} 详情失败: 页面提示帖子不存在或404。")
                return None
            print(f"成功获取到帖子 {post_id} 的页面内容。")
            return self._parse_post_detail(html_content, post_id, url)
        except Exception as e:
            print(f"使用浏览器获取帖子 {post_id} 详情时发生异常: {e}")
            return None
        finally:
            if driver:
                try: driver.quit()
                except: pass

    def _parse_post_detail(self, html_content: str, post_id: int, url: str) -> Optional[ForumPost]:
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            title_elem = soup.select_one('h1.post-title, .post-title h1')
            title = title_elem.get_text(strip=True) if title_elem else "未知标题"
            content_elem = soup.select_one('article.post-content')
            content = content_elem.get_text(strip=True) if content_elem else ""
            author_elem = soup.select_one('.author-name')
            author = author_elem.get_text(strip=True) if author_elem else "未知作者"
            return ForumPost(post_id=post_id, title=title, content=content, author=author, author_id=0, category="", created_time=datetime.now(), reply_count=0, view_count=0, url=url)
        except Exception as e:
            print(f"解析帖子 {post_id} 详情失败: {e}")
            return None
    
    def post_comment(self, post_id: int, content: str) -> Tuple[bool, str]:
        driver = None
        try:
            driver = self._setup_driver()
            if not driver: return False, "浏览器驱动初始化失败。"
            post_url = f'{self.config.base_url}/post-{post_id}-1'
            print(f"正在使用Selenium访问帖子: {post_url}")
            driver.get(post_url)
            print("等待评论框加载...")
            editor_container = WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.CSS_SELECTOR, '.CodeMirror')))
            editor_input_area = driver.find_element(By.CSS_SELECTOR, '.CodeMirror-scroll')
            editor_input_area.click()
            time.sleep(0.5)
            actions = ActionChains(driver)
            actions.send_keys(content).perform()
            print("内容输入完成，准备提交...")
            time.sleep(2)
            submit_button = WebDriverWait(driver, 30).until(EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'submit') and contains(text(), '发布评论')]")))
            driver.execute_script("arguments[0].scrollIntoView(true);", submit_button)
            time.sleep(0.5)
            submit_button.click()
            print(f"评论已在帖子 {post_url} 中提交")
            time.sleep(3)
            return True, "评论已通过浏览器模拟成功提交"
        except Exception as e:
            print(f"使用Selenium评论时出错: {e}")
            import traceback
            traceback.print_exc()
            return False, f"使用Selenium评论时出错: {e}"
        finally:
            if driver:
                try: driver.quit()
                except: pass
    
    # (省略了 get_categories, test_connection 等其他未修改的函数的完整代码)
    def get_categories(self) -> List[Dict]:
        try:
            url = f"{self.config.base_url}/api/content/list-categories"
            headers = self.session.headers.copy()
            response = self.session.post(url, headers=headers)
            if response.status_code == 200: return response.json().get('data', [])
            else:
                print(f"获取分类列表失败: {response.status_code}")
                return []
        except Exception as e:
            print(f"获取分类列表异常: {e}")
            return []
    def get_account_info(self, user_id: int) -> Optional[Dict]:
        try:
            url = f"{self.config.base_url}/api/account/getInfo/{user_id}"
            response = self.session.get(url, headers=self.session.headers)
            if response.status_code == 200: return response.json()
            else:
                print(f"获取用户信息失败: {response.status_code}")
                return None
        except Exception as e:
            print(f"获取用户信息异常: {e}")
            return None
    def get_unread_notifications(self) -> Optional[Dict]:
        try:
            url = f"{self.config.base_url}/api/notification/unread-count"
            response = self.session.get(url, headers=self.session.headers)
            if response.status_code == 200: return response.json()
            else:
                print(f"获取通知失败: {response.status_code}")
                return None
        except Exception as e:
            print(f"获取通知异常: {e}")
            return None
    def ping(self) -> bool:
        try:
            url = f"{self.config.base_url}/edge-cgi/ping"
            response = self.session.get(url, headers=self.session.headers)
            return response.status_code == 200
        except Exception: return False
    def test_connection(self) -> Dict[str, bool]:
        results = {'ping': False, 'get_categories': False, 'get_notifications': False, 'overall': False}
        try:
            results['ping'] = self.ping()
            categories = self.get_categories()
            results['get_categories'] = len(categories) > 0
            notifications = self.get_unread_notifications()
            results['get_notifications'] = notifications is not None
            results['overall'] = all([results['ping'], results['get_categories']])
        except Exception as e:
            print(f"连接测试异常: {e}")
        return results
if __name__ == "__main__":
    from ..config.config_manager import ConfigManager
    config_manager = ConfigManager()
    forum_config = config_manager.get_forum_config()
    client = DeepFloodClient(forum_config)
    print("测试连接...")
    results = client.test_connection()
    for key, value in results.items(): print(f"  {key}: {'✓' if value else '✗'}")
    print("\n获取帖子列表...")
    posts = client.get_post_list_from_rss()
    print(f"获取到 {len(posts)} 个帖子")
    if posts:
        first_post = posts[0]
        print(f"\n获取帖子详情: {first_post['title']}")
        detail = client.get_post_detail(first_post['post_id'])
        if detail:
            print(f"  标题: {detail.title}")
            print(f"  作者: {detail.author}")
            print(f"  内容长度: {len(detail.content)}")
