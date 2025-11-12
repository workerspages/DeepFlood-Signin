"""
DeepFlood论坛API客户端
"""
import requests
from curl_cffi import requests as cffi_requests
import time
import json
import os
import re
import random
from typing import Dict, List, Optional, Tuple
from bs4 import BeautifulSoup
from dataclasses import dataclass
from datetime import datetime
import xml.etree.ElementTree as ET
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from urllib.parse import urlparse
from ..config.config_manager import ForumConfig
import logging

# 配置此模块的日志记录器
logger = logging.getLogger(__name__)

@dataclass
class ForumPost:
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

class DeepFloodClient:
    def __init__(self, config: ForumConfig):
        self.config = config
        self.session_cookie = config.session_cookie
        self.cookies = self._parse_cookie(config.session_cookie)

    def _parse_cookie(self, cookie_str: str) -> Dict[str, str]:
        cookies = {}
        if not cookie_str:
            return cookies
        for item in cookie_str.split(';'):
            if '=' in item:
                key, value = item.strip().split('=', 1)
                cookies[key] = value
        return cookies

    def _save_cookies_from_driver(self, driver):
        try:
            current_cookies = driver.get_cookies()
            if not current_cookies:
                return
            required_keys = ['cf_clearance', 'session', 'smac', 'fog']
            filtered_cookies = [c for c in current_cookies if c['name'] in required_keys]
            if len(filtered_cookies) < len(required_keys):
                return
            new_cookie_string = "; ".join([f"{c['name']}={c['value']}" for c in filtered_cookies])
            if new_cookie_string and new_cookie_string != self.session_cookie:
                cookie_data = {"cookie_string": new_cookie_string, "updated_at": datetime.now().isoformat()}
                os.makedirs(os.path.dirname(self.config.cookie_file_path), exist_ok=True)
                with open(self.config.cookie_file_path, 'w', encoding='utf-8') as f:
                    json.dump(cookie_data, f, ensure_ascii=False, indent=2)
                logger.info(f"已将最新Cookie保存到 {self.config.cookie_file_path}")
                self.session_cookie = new_cookie_string
        except Exception as e:
            logger.error(f"保存最新Cookie时发生错误: {e}")

    def setup_driver(self):
        try:
            logger.info("创建并设置共享浏览器实例...")
            options = uc.ChromeOptions()
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--headless')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size=1920,1080')
            options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            kwargs = {'options': options}
            if os.getenv('DRIVER_EXECUTABLE_PATH'):
                kwargs['executable_path'] = os.getenv('DRIVER_EXECUTABLE_PATH')
            if os.getenv('CHROME_VERSION') and os.getenv('CHROME_VERSION').isdigit():
                kwargs['version_main'] = int(os.getenv('CHROME_VERSION'))
            
            driver = uc.Chrome(**kwargs)

            # 【重要修正】给浏览器进程一点反应时间来完全初始化
            time.sleep(2)
            
            driver.get(self.config.base_url)
            time.sleep(2)
            for name, value in self.cookies.items():
                driver.add_cookie({'name': name, 'value': value, 'domain': '.deepflood.com', 'path': '/'})
            driver.refresh()
            time.sleep(5)
            self._save_cookies_from_driver(driver)
            return driver
        except Exception as e:
            logger.error(f"设置浏览器和Cookie时出错: {e}", exc_info=True)
            return None

    def get_post_list_from_rss(self) -> List[Dict]:
        try:
            response = requests.get("https://feed.deepflood.com/topic.rss.xml", timeout=30)
            if response.status_code == 200:
                root = ET.fromstring(response.text)
                posts = []
                for item in root.findall('.//item'):
                    link = item.find('link').text
                    match = re.search(r'/post-(\d+)-', link)
                    if match:
                        posts.append({'post_id': int(match.group(1)), 'title': item.find('title').text or ''})
                return posts
            return []
        except Exception as e:
            logger.error(f"获取RSS异常: {e}")
            return []

    def get_post_detail(self, post_id: int, driver) -> Optional[ForumPost]:
        try:
            url = f"{self.config.base_url}/post-{post_id}-1"
            driver.get(url)
            WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'article.post-content')))
            time.sleep(random.uniform(1.5, 2.5))
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            title = soup.select_one('h1.post-title, .post-title h1').get_text(strip=True)
            content = soup.select_one('article.post-content').get_text(strip=True)
            author = soup.select_one('.author-name').get_text(strip=True)
            return ForumPost(post_id=post_id, title=title, content=content, author=author, url=url, author_id=0, category="", created_time=datetime.now(), reply_count=0, view_count=0)
        except Exception as e:
            logger.error(f"使用浏览器获取帖子 {post_id} 详情时发生异常: {e}")
            return None

    def post_comment(self, post_id: int, content: str, driver) -> Tuple[bool, str]:
        try:
            post_url = f'{self.config.base_url}/post-{post_id}-1'
            driver.get(post_url)
            editor_container = WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.CSS_SELECTOR, '.CodeMirror')))
            ActionChains(driver).click(editor_container).send_keys(content).perform()
            time.sleep(2)
            submit_button = WebDriverWait(driver, 30).until(EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'submit') and contains(text(), '发布评论')]")))
            driver.execute_script("arguments[0].scrollIntoView(true);", submit_button)
            time.sleep(0.5)
            submit_button.click()
            time.sleep(3)
            return True, "评论成功提交"
        except Exception as e:
            logger.error(f"使用Selenium评论时出错: {e}", exc_info=True)
            return False, str(e)
