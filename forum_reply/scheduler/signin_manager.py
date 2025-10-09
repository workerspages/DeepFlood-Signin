# -- coding: utf-8 --
"""
Copyright (c) 2024 [Hosea]
Licensed under the MIT License.
See LICENSE file in the project root for full license information.
"""
import os
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
import logging

logger = logging.getLogger(__name__)

class SignInManager:
    def __init__(self, cookie: str, random_bonus: bool, headless: bool):
        self.cookie = cookie
        self.ns_random = random_bonus
        self.headless = headless

    def click_sign_icon(self, driver):
        """
        尝试点击签到图标和试试手气按钮的通用方法
        """
        try:
            logger.info("开始查找签到图标...")
            sign_icon = WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.XPATH, "//span[@title='签到']"))
            )
            logger.info("找到签到图标，准备点击...")
            
            driver.execute_script("arguments[0].scrollIntoView(true);", sign_icon)
            time.sleep(0.5)
            
            logger.info(f"签到图标元素: {sign_icon.get_attribute('outerHTML')}")
            
            try:
                sign_icon.click()
                logger.info("签到图标点击成功")
            except Exception as click_error:
                logger.info(f"点击失败，尝试使用 JavaScript 点击: {str(click_error)}")
                driver.execute_script("arguments[0].click();", sign_icon)
            
            logger.info("等待页面跳转...")
            time.sleep(5)
            
            logger.info(f"当前页面URL: {driver.current_url}")
            
            try:
                click_button:None
                
                if self.ns_random:
                    click_button = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), '试试手气')]"))
                )
                else:
                    click_button = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), '鸡腿 x 5')]"))
                )
                
                click_button.click()
                logger.info("完成试试手气点击")
            except Exception as lucky_error:
                logger.info(f"试试手气按钮点击失败或者签到过了: {str(lucky_error)}")
                
            return True
            
        except Exception as e:
            logger.error(f"签到过程中出错:")
            logger.error(f"错误类型: {type(e).__name__}")
            logger.error(f"错误信息: {str(e)}")
            logger.error(f"当前页面URL: {driver.current_url}")
            logger.error(f"当前页面源码片段: {driver.page_source[:500]}...")
            logger.error("详细错误信息:", exc_info=True)
            return False

    def setup_driver_and_cookies(self):
        """
        初始化浏览器并设置cookie的通用方法
        返回: 设置好cookie的driver实例
        """
        try:
            if not self.cookie:
                logger.error("未找到cookie配置")
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
            
            logger.info("正在启动Chrome...")
            driver = uc.Chrome(options=options, version_main=140)
            
            if self.headless:
                driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                driver.set_window_size(1920, 1080)
            
            logger.info("Chrome启动成功")
            
            logger.info("正在设置cookie...")
            driver.get('https://www.deepflood.com')
            
            time.sleep(5)
            
            for cookie_item in self.cookie.split(';'):
                try:
                    name, value = cookie_item.strip().split('=', 1)
                    driver.add_cookie({
                        'name': name, 
                        'value': value, 
                        'domain': '.deepflood.com',
                        'path': '/'
                    })
                except Exception as e:
                    logger.warning(f"设置cookie出错: {str(e)}")
                    continue
            
            logger.info("刷新页面...")
            driver.refresh()
            time.sleep(5)
            
            return driver
            
        except Exception as e:
            logger.error(f"设置浏览器和Cookie时出错: {str(e)}", exc_info=True)
            return None

    def run_signin(self):
        logger.info("开始执行DeepFlood签到...")
        driver = self.setup_driver_and_cookies()
        if not driver:
            logger.error("浏览器初始化失败")
            return
        
        try:
            self.click_sign_icon(driver)
            logger.info("签到任务完成")
        finally:
            driver.quit()
            logger.info("浏览器已关闭")
