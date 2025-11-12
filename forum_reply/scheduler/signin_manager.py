# -- coding: utf-8 --
import os
import json
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from selenium.webdriver.common.action_chains import ActionChains
import logging

logger = logging.getLogger(__name__)

class SignInManager:
    # 【重要修改】__init__ 简化，不再需要 cookie 和文件路径
    def __init__(self, random_bonus: bool):
        self.ns_random = random_bonus

    def click_sign_icon(self, driver):
        try:
            logger.info("开始查找签到图标...")
            sign_icon = WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.XPATH, "//span[@title='签到']")))
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center', inline: 'nearest'});", sign_icon)
            time.sleep(1)
            ActionChains(driver).move_to_element(sign_icon).click().perform()
            logger.info("点击签到图标成功")
            time.sleep(5)
            try:
                wait = WebDriverWait(driver, 15)
                button_xpath = "//button[contains(text(), '试试手气') or contains(text(), '鸡腿')]"
                click_button = wait.until(EC.element_to_be_clickable((By.XPATH, button_xpath)))
                click_button.click()
                logger.info(f"成功点击签到奖励按钮。")
            except Exception:
                logger.info("未找到签到奖励按钮，可能已经签到过了。")
        except Exception as e:
            logger.error(f"签到过程中出错: {e}", exc_info=True)

    # 【重要修改】run_signin 接受一个 driver 参数
    def run_signin(self, driver):
        logger.info("开始执行DeepFlood签到...")
        if not driver:
            logger.error("没有可用的浏览器实例，无法执行签到。")
            raise Exception("No valid driver provided to SignInManager")
        
        self.click_sign_icon(driver)
        logger.info("签到任务完成。")

    # 【重要修改】移除 setup_driver_and_cookies 和 quit 方法
