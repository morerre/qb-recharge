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

def drag_slider_human(page):
    """
    专门针对 <div id="slider"> 的拖动验证，模拟更真实的轨迹。
    返回 True 如果验证码消失或页面跳转。
    """
    slider = page.query_selector('#slider')
    if not slider:
        return False
    handler = page.query_selector('#slider .handler')
    if not handler:
        return False

    # 等待滑块可见
    try:
        handler.wait_for(state='visible', timeout=3000)
    except:
        pass

    box = handler.bounding_box()
    slider_box = slider.bounding_box()
    if not box or not slider_box:
        return False

    # 计算起始和目标位置
    start_x = box['x'] + box['width'] / 2
    start_y = box['y'] + box['height'] / 2
    # 目标位置：滑轨最右端减去滑块一半宽度，留一点间隙
    target_x = slider_box['x'] + slider_box['width'] - box['width'] / 2 - random.uniform(1, 3)

    # 鼠标移动到滑块起始位置（稍微偏移一点，模拟真实点击偏差）
    page.mouse.move(start_x + random.uniform(-1, 1), start_y + random.uniform(-1, 1))
    time.sleep(random.uniform(0.05, 0.15))
    page.mouse.down()

    # 人类拖动轨迹：慢速开始，中间加速，末端减速，有时回退
    total_distance = target_x - start_x
    current_x = start_x
    steps = random.randint(30, 50)
    for i in range(steps):
        remaining = target_x - current_x
        # 速度曲线：先慢后快再慢
        progress = (i / steps)
        if progress < 0.2:
            speed = random.uniform(0.05, 0.15)
        elif progress < 0.8:
            speed = random.uniform(0.15, 0.35)
        else:
            speed = random.uniform(0.03, 0.1)

        move = remaining * speed
        # 加入微小回退（1/5的概率）
        if random.random() < 0.2 and i > 5:
            move *= -random.uniform(0.05, 0.15)
            current_x += move
            current_y = start_y + random.uniform(-2, 2)
            page.mouse.move(current_x, current_y)
            time.sleep(random.uniform(0.01, 0.03))
            continue

        current_x += move
        current_y = start_y + random.uniform(-1, 1)
        page.mouse.move(current_x, current_y)
        # 随机停顿
        if random.random() < 0.08:
            time.sleep(random.uniform(0.02, 0.08))
        else:
            time.sleep(random.uniform(0.003, 0.01))

    # 最后微调到位
    page.mouse.move(target_x, start_y + random.uniform(-1, 1))
    time.sleep(random.uniform(0.05, 0.15))
    page.mouse.up()
    time.sleep(0.5)

    # 等待验证结果（最多等待 3 秒）
    try:
        page.wait_for_function(
            "!document.querySelector('#slider') || document.querySelector('#slider .handler').style.left === '0px'",
            timeout=3000
        )
    except:
        pass

    # 检查滑块是否消失或 handler 的 left 是否变了（验证成功时通常会移回0或消失）
    if not page.query_selector('#slider'):
        return True
    handler_after = page.query_selector('#slider .handler')
    if handler_after:
        left = handler_after.get_attribute('style')
        if left and 'left: 0px' in left:
            return True
    # 也可能页面跳转了
    if '/checkout' not in page.url:
        return True
    return False

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
            # 加载页面（重试3次）
            for attempt in range(3):
                try:
                    page.goto(args.url, wait_until='domcontentloaded', timeout=60000)
                    break
                except PlaywrightTimeout:
                    print(f"超时重试 {attempt+1}/3", file=sys.stderr)
                    time.sleep(2)
            else:
                raise Exception("页面加载失败")

            # 检测验证码
            content = page.content()
            has_slider = page.query_selector('#slider')
            if '滑动验证' in content or 'verify' in content.lower() or has_slider:
                print("检测到验证码，开始自动验证...", file=sys.stderr)
                success = False
                for retry in range(3):
                    print(f"验证尝试 {retry+1}/3", file=sys.stderr)
                    if drag_slider_human(page):
                        success = True
                        break
                    # 如果失败，刷新页面重试
                    if retry < 2:
                        print("刷新页面重试...", file=sys.stderr)
                        page.reload(wait_until='domcontentloaded')
                        time.sleep(2)
                if success:
                    print("验证成功！", file=sys.stderr)
                    cookies = context.cookies()
                    print(json.dumps([{'name': c['name'], 'value': c['value'], 'domain': c.get('domain', ''), 'path': c.get('path', '/')} for c in cookies]))
                    print("IP 已激活！", file=sys.stderr)
                else:
                    print("多次尝试后仍未通过验证", file=sys.stderr)
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