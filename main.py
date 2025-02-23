from playwright.sync_api import sync_playwright, TimeoutError
import time
import datetime
import sys
import logging
import random

# 常量定义
LOGIN_TIMEOUT = 20000  # 登录等待时间（毫秒）
PAGE_LOAD_TIMEOUT = 5000  # 页面加载超时时间（毫秒）
NETWORK_IDLE_TIMEOUT = 5000  # 网络空闲等待时间（毫秒）
CLICK_TIMEOUT = 1000  # 点击操作超时时间（毫秒）
MAX_SUBMIT_RETRIES = 100  # 最大提交重试次数
MAX_SETTLEMENT_RETRIES = 100  # 最大结算重试次数
SUBMIT_RETRY_INTERVAL = 10  # 提交重试间隔（毫秒）
SETTLEMENT_RETRY_INTERVAL = 10  # 结算重试间隔（毫秒）
CLICK_RETRY_INTERVAL = 500  # 点击重试间隔（毫秒）
MAX_PAGE_LOAD_RETRIES = 3  # 页面加载最大重试次数

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('taobao_bot.log')
    ]
)

def wait_for_network_idle(page, timeout=NETWORK_IDLE_TIMEOUT):
    """等待网络状态稳定"""
    try:
        page.wait_for_load_state("networkidle", timeout=timeout)
        return True
    except TimeoutError:
        logging.warning("网络状态等待超时，继续执行")
        return True  # 即使超时也继续执行

def retry_click(page, selector, max_retries=3, timeout=CLICK_TIMEOUT):
    """重试点击元素"""
    for i in range(max_retries):
        try:
            element = page.locator(selector)
            if element.is_visible(timeout=timeout):
                element.click()
                return True
            else:
                logging.warning(f"元素 {selector} 不可见，重试 {i+1}/{max_retries}")
        except Exception as e:
            logging.warning(f"点击失败 {selector}，重试 {i+1}/{max_retries}: {str(e)}")
        time.sleep(CLICK_RETRY_INTERVAL / 1000)  # 转换为秒
    return False

def load_page_with_retry(page, url, max_retries=MAX_PAGE_LOAD_RETRIES):
    """带重试的页面加载"""
    for i in range(max_retries):
        try:
            # 设置较长的超时时间
            page.set_default_timeout(PAGE_LOAD_TIMEOUT)
            page.set_default_navigation_timeout(PAGE_LOAD_TIMEOUT)
            
            # 尝试加载页面
            response = page.goto(url)
            if response:
                # 等待页面加载完成
                page.wait_for_load_state("domcontentloaded")
                # 等待网络状态稳定
                wait_for_network_idle(page)
                return True
            
            logging.warning(f"页面加载重试 {i+1}/{max_retries}")
                
        except Exception as e:
            logging.error(f"页面加载失败 {i+1}/{max_retries}: {str(e)}")
            if i == max_retries - 1:  # 最后一次重试失败
                raise
            
        time.sleep(2)  # 重试前等待
    return False

def random_sleep():
    """随机等待一段时间"""
    sleep_time = random.uniform(0.1, 0.3)  # 100ms到300ms之间的随机时间
    time.sleep(sleep_time)

def wait_until_time(target_time):
    """等待直到目标时间"""
    while True:
        current_time = datetime.datetime.now()
        if current_time >= target_time:
            break

def main():
    try:
        start_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
        logging.info(f"程序启动时间: {start_time}")

        # 获取目标时间
        target_time_str = input("请输入目标时间（格式：2024-02-23 12:00:00）：")
        target_time = datetime.datetime.strptime(target_time_str, '%Y-%m-%d %H:%M:%S')
        logging.info(f"目标时间: {target_time_str}")

        with sync_playwright() as p:
            try:
                # 启动浏览器，添加更多配置
                browser = p.chromium.launch(
                    headless=False,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-web-security',  # 禁用跨域限制
                        '--disable-features=IsolateOrigins,site-per-process'  # 禁用站点隔离
                    ]
                )
                context = browser.new_context(
                    viewport={'width': 1280, 'height': 800},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                )
                
                # 设置默认超时
                context.set_default_timeout(PAGE_LOAD_TIMEOUT)
                context.set_default_navigation_timeout(PAGE_LOAD_TIMEOUT)
                
                page = context.new_page()

                # 设置请求拦截
                page.route("**/*", lambda route: route.continue_())
                
                # 监听console消息
                page.on("console", lambda msg: logging.debug(f"浏览器控制台: {msg.text}"))

                # 登录淘宝
                logging.info("正在打开淘宝登录页面...")
                if not load_page_with_retry(page, "https://www.taobao.com"):
                    raise Exception("淘宝首页加载失败")

                if not retry_click(page, "text=亲，请登录"):
                    raise Exception("无法找到登录按钮")

                logging.info("等待手动登录...")
                page.wait_for_timeout(LOGIN_TIMEOUT)

                # 检查登录状态
                if not page.locator(".site-nav-login-info-nick").is_visible(timeout=PAGE_LOAD_TIMEOUT):
                    raise Exception("登录失败或超时")

                logging.info("登录成功，正在跳转购物车页面...")
                if not load_page_with_retry(page, "https://cart.taobao.com/cart.htm"):
                    raise Exception("购物车页面加载失败")
                
                # # 点击全选按钮
                # if not retry_click(page, "//*[contains(@class, 'cartOperationCheckbox--CIlk23mK')]/span[1]/input[1]"):
                #     raise Exception("点击全选按钮失败")
                # logging.info("已点击全选按钮")

                logging.info("等待目标时间...")
                wait_until_time(target_time)

                logging.info("开始执行抢购...")
                # 点击结算按钮（带重试机制）
                settlement_retry_count = 0
                while settlement_retry_count < MAX_SETTLEMENT_RETRIES:
                    try:
                        if retry_click(page, "//*[contains(@class, 'btn--QDjHtErD')]"):
                            logging.info("已点击结算按钮")
                            break
                        else:
                            logging.warning(f"未找到结算按钮，重试中...")
                    except Exception as e:
                        logging.debug(f"结算按钮重试 {settlement_retry_count + 1}/{MAX_SETTLEMENT_RETRIES}: {str(e)}")
                        settlement_retry_count += 1
                        random_sleep()
                        page.wait_for_timeout(SETTLEMENT_RETRY_INTERVAL)

                    if settlement_retry_count >= MAX_SETTLEMENT_RETRIES:
                        raise Exception("点击结算按钮失败，超过最大重试次数")

                # 等待提交订单按钮出现并点击
                retry_count = 0
                while retry_count < MAX_SUBMIT_RETRIES:
                    try:
                        if retry_click(page, "//*[contains(@class, 'btn--QDjHtErD')]"):
                            logging.info("抢购成功，请尽快付款！")
                            # 保持程序运行，等待用户付款
                            while True:
                                time.sleep(1)
                        else:
                            logging.warning("未找到提交订单按钮，重试中...")
                    except Exception as e:
                        logging.debug(f"提交订单重试 {retry_count + 1}/{MAX_SUBMIT_RETRIES}: {str(e)}")
                        retry_count += 1
                        random_sleep()
                        page.wait_for_timeout(SUBMIT_RETRY_INTERVAL)

                    if retry_count >= MAX_SUBMIT_RETRIES:
                        logging.error("提交订单失败，超过最大重试次数")
                        break

            except Exception as e:
                logging.error(f"运行过程中出现错误: {str(e)}")
            finally:
                try:
                    browser.close()
                except:
                    pass

    except Exception as e:
        logging.error(f"程序异常: {str(e)}")
        input("按回车键退出...")

if __name__ == "__main__":
    main()
