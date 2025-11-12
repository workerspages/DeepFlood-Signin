# -- coding: utf-8 --
"""
Copyright (c) 2024 [Hosea]
Licensed under the MIT License.
See LICENSE file in the project root for full license information.
"""
import os
import json
from datetime import datetime
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import random
import time
import traceback
import undetected_chromedriver as uc
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from urllib.parse import urlparse
import logging

logger = logging.getLogger(__name__)

class SignInManager:
    def __init__(self, cookie: str, random_bonus: bool, headless: bool, cookie_file_path: str):
        self.initial_cookie_str = cookie
        self.ns_random = random_bonus
        self.headless = headless
        self.cookie_file_path = cookie_file_path
        self.driver = None

    def _save_cookies_from_driver(self, driver):
        """从浏览器实例获取最新Cookie并保存到持久化文件"""
        try:
            current_cookies = driver.get_cookies()
            if not current_cookies:
                logger.warning("未能从浏览器中获取到任何Cookie。")
                return

            # 过滤掉非必要的Cookie，只保留关键的几个，以保持整洁
            required_keys = ['cf_clearance', 'session', 'smac', 'fog']
            filtered_cookies = [c for c in current_cookies if c['name'] in required_keys]
            
            # 确保所有关键Cookie都被获取到了
            if len(filtered_cookies) < len(required_keys):
                logger.warning(f"获取到的关键Cookie不完整，跳过保存。需要 {required_keys}, 实际获取 {[c['name'] for c in filtered_cookies]}")
                return

            new_cookie_string = "; ".join([f"{c['name']}={c['value']}" for c in filtered_cookies])

            # 只有当Cookie发生显著变化时才写入文件
            if new_cookie_string and new_cookie_string != self.initial_cookie_str:
                cookie_data = {
                    "cookie_string": new_cookie_string,
                    "updated_at": datetime.now().isoformat()
                }
                
                os.makedirs(os.path.dirname(self.cookie_file_path), exist_ok=True)
                with open(self.cookie_file_path, 'w', encoding='utf-8') as f:
                    json.dump(cookie_data, f, ensure_ascii=False, indent=2)
                
                logger.info(f"检测到Cookie更新，已将最新Cookie保存到 {self.cookie_file_path}")
            else:
                logger.info("Cookie未发生变化，无需更新。")

        except Exception as e:
            logger.error(f"保存最新Cookie时发生错误: {e}")

    def click_sign_icon(self, driver):
        """尝试点击签到图标和奖励按钮"""
        try:
            logger.info("开始查找签到图标...")
            sign_icon = WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.XPATH, "//span[@title='签到']"))
            )
            
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center', inline: 'nearest'});", sign_icon)
            time.sleep(1)
            
            ActionChains(driver).move_to_element(sign_icon).click().perform()
            logger.info("ActionChains 点击签到图标成功")
            
            time.sleep(5)
            
            try:
                wait = WebDriverWait(driver, 15)
                button_xpath = "//button[contains(text(), '试试手气') or contains(text(), '鸡腿')]"
                click_button = wait.until(
                    EC.element_to_be_clickable((By.XPATH, button_xpath))
                )
                button_text = click_button.text
                click_button.click()
                logger.info(f"成功点击签到奖励按钮: '{button_text}'")
            except Exception:
                logger.info("未找到签到奖励按钮，可能已经签到过了。")
                
            return True
            
        except Exception as e:
            logger.error(f"签到过程中出错:")
            logger.error(f"错误类型: {type(e).__name__}")
            logger.error(f"错误信息: {str(e)}")
            logger.error(f"当前页面URL: {driver.current_url}")
            logger.error("详细错误信息:", exc_info=True)
            return False

    def setup_driver_and_cookies(self):
        """初始化浏览器，并在加载后立即保存更新的Cookie"""
        try:
            if not self.initial_cookie_str:
                logger.error("未找到初始Cookie配置")
                return None
                
            logger.info("开始初始化浏览器...")
            options = uc.ChromeOptions()
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            
            if self.headless:
                logger.info("启用无头模式...")
                options.add_argument('--headless')
                options.add_argument('--disable-blink-features=AutomationControlled')
                options.add_argument('--disable-gpu')
                options.add_argument('--window-size=1920,1080')
            
            options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            driver_executable_path = os.getenv('DRIVER_EXECUTABLE_PATH')
            chrome_version_str = os.getenv('CHROME_VERSION')

            kwargs = {'options': options}
            if driver_executable_path:
                kwargs['executable_path'] = driver_executable_path
            if chrome_version_str and chrome_version_str.isdigit():
                kwargs['version_main'] = int(chrome_version_str)
            
            self.driver = uc.Chrome(**kwargs)
            self.driver.__del__ = lambda: None
            
            logger.info("Chrome启动成功，正在设置初始Cookie...")
            self.driver.get('https://www.deepflood.com')
            time.sleep(2)
            
            cookies_dict = {item.split('=')[0].strip(): item.split('=', 1)[1].strip() for item in self.initial_cookie_str.split(';') if '=' in item}

            for name, value in cookies_dict.items():
                self.driver.add_cookie({
                    'name': name,
                    'value': value,
                    'domain': '.deepflood.com',
                    'path': '/'
                })
            
            logger.info("刷新页面以应用Cookie并获取服务器更新...")
            self.driver.refresh()
            time.sleep(5)  # 等待页面完全加载，确保所有Cookie都已更新
            
            # 在成功加载后，立即调用保存Cookie的函数
            self._save_cookies_from_driver(self.driver)
            
            return self.driver
            
        except Exception as e:
            logger.error(f"设置浏览器和Cookie时出错: {e}", exc_info=True)
            return None

    def run_signin(self):
        logger.info("开始执行DeepFlood签到和Cookie刷新...")
        self.driver = self.setup_driver_and_cookies()
        if not self.driver:
            logger.error("浏览器初始化失败，无法执行签到。")
            # 抛出异常，让上层知道失败了
            raise Exception("Browser initialization failed in SignInManager")
        
        self.click_sign_icon(self.driver)
        logger.info("签到任务完成。")

    def quit(self):
        """关闭浏览器"""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("浏览器已关闭")
            except Exception as e:
                logger.error(f"关闭浏览器时出错: {e}", exc_info=True)
            finally:
                self.driver = None
