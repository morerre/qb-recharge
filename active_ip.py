#!/usr/bin/env python3
import sys, time, random, json, argparse
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

def create_stealth_context(browser, proxy=None):
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
    ]
    context_options = {
        'user_agent': random.choice(user_agents),
        'viewport': {'width': 1280, 'height': 720},
        'locale': 'zh-CN',
        'timezone_id': 'Asia/Shanghai',
        'geolocation': {'latitude': 31.2304, 'longitude': 121.4737},
        'permissions': ['geolocation'],
    }
    if proxy:
        context_options['proxy'] = {'server': proxy}
    context = browser.new_context(**context_options)
    context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => false });
        window.chrome = { runtime: {} };
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
        Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh'] });
    """)
    return context

def drag_slider(page):
    """专门针对 <div id="slider"> 的拖动验证"""
    slider = page.query_selector('#slider')
    if not slider:
        return False
    handler = page.query_selector('#slider .handler')
    if not handler:
        return False
    box = handler.bounding_box()
    slider_box = slider.bounding_box()
    if not box or not slider_box:
        return False

    start_x = box['x'] + box['width'] / 2
    start_y = box['y'] + box['height'] / 2
    target_x = slider_box['x'] + slider_box['width'] - box['width'] / 2 - 2

    page.mouse.move(start_x, start_y)
    page.mouse.down()
    steps = random.randint(25, 40)
    current_x = start_x
    for i in range(steps):
        remaining = target_x - current_x
        move = remaining * random.uniform(0.05, 0.2)
        current_x += move
        current_y = start_y + random.uniform(-1, 1)
        page.mouse.move(current_x, current_y)
        time.sleep(random.uniform(0.005, 0.02))
        if random.random() < 0.05:
            time.sleep(random.uniform(0.03, 0.1))
    page.mouse.move(target_x, start_y + random.uniform(-1, 1))
    time.sleep(random.uniform(0.08, 0.15))
    page.mouse.up()
    time.sleep(1)
    return True

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('url', nargs='?', default='https://www.whquxinyong.xyz/checkout')
    parser.add_argument('--proxy', default=None)
    args = parser.parse_args()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox',
                  '--disable-blink-features=AutomationControlled']
        )
        context = create_stealth_context(browser, args.proxy)
        page = context.new_page()
        page.set_default_timeout(60000)
        try:
            print(f"访问: {args.url}", file=sys.stderr)
            for attempt in range(3):
                try:
                    page.goto(args.url, wait_until='domcontentloaded', timeout=60000)
                    break
                except PlaywrightTimeout:
                    print(f"超时重试 {attempt+1}/3", file=sys.stderr)
                    time.sleep(2)
            else:
                raise Exception("页面加载失败")

            content = page.content()
            if '滑动验证' in content or 'verify' in content.lower() or page.query_selector('#slider'):
                print("检测到验证码，开始自动验证...", file=sys.stderr)
                if drag_slider(page):
                    # 等待页面变化
                    try:
                        page.wait_for_load_state('networkidle', timeout=10000)
                    except:
                        pass
                    time.sleep(2)
                    # 判断验证是否通过（滑块消失或页面跳转）
                    if not page.query_selector('#slider'):
                        print("验证成功！", file=sys.stderr)
                        cookies = context.cookies()
                        print(json.dumps([{'name': c['name'], 'value': c['value'], 'domain': c.get('domain', ''), 'path': c.get('path', '/')} for c in cookies]))
                        print("IP 已激活！", file=sys.stderr)
                    else:
                        print("验证可能失败（滑块仍在）", file=sys.stderr)
                        sys.exit(1)
                else:
                    print("拖动失败", file=sys.stderr)
                    sys.exit(1)
            else:
                print("未检测到验证码，可能已激活", file=sys.stderr)
                cookies = context.cookies()
                print(json.dumps([{'name': c['name'], 'value': c['value'], 'domain': c.get('domain', ''), 'path': c.get('path', '/')} for c in cookies]))
        except Exception as e:
            print(f"异常: {e}", file=sys.stderr)
            sys.exit(1)
        finally:
            browser.close()

if __name__ == '__main__':
    main()