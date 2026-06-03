#!/usr/bin/env python3
"""
独立脚本：使用 Playwright 打开目标页面，自动完成滑动验证，激活当前 IP 的信任状态。
用法:
    python3 active_ip.py [url] [--proxy http://user:pass@ip:port]
默认 url 为 https://www.whquxinyong.xyz/checkout
"""
import sys
import time
import random
import argparse
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

def human_like_drag(page, slider_selector, distance=None):
    """
    模拟人类拖动滑块。
    如果提供了 distance（滑动距离），直接使用；否则自动计算滑轨宽度。
    """
    # 等待滑块出现
    slider = page.wait_for_selector(slider_selector, timeout=5000)
    if not slider:
        print("未找到滑块元素", file=sys.stderr)
        return False

    box = slider.bounding_box()
    if not box:
        print("无法获取滑块位置", file=sys.stderr)
        return False

    start_x = box['x'] + box['width'] / 2
    start_y = box['y'] + box['height'] / 2

    # 如果没有指定距离，尝试自动获取滑轨宽度（极验通常有一个 track 元素）
    if distance is None:
        # 尝试查找常见的滑轨元素
        track = page.query_selector('.geetest_slider_track, .slideTrack, [class*="track"]')
        if track:
            track_box = track.bounding_box()
            distance = track_box['width'] - box['width'] - 4  # 留一点余量
        else:
            # 兜底：假设滑轨宽度为 300px
            distance = 300

    target_x = start_x + distance

    # 模拟人类拖动轨迹
    page.mouse.move(start_x, start_y)
    page.mouse.down()

    # 生成随机停顿点和移动步长
    steps = random.randint(15, 30)
    current_x = start_x
    for i in range(steps):
        remaining = target_x - current_x
        move = remaining * random.uniform(0.05, 0.25)
        current_x += move
        current_y = start_y + random.uniform(-2, 2)
        page.mouse.move(current_x, current_y)
        time.sleep(random.uniform(0.01, 0.04))
        # 偶尔停顿
        if random.random() < 0.15:
            time.sleep(random.uniform(0.05, 0.15))

    # 最后精确移动到目标位置
    page.mouse.move(target_x, start_y + random.uniform(-1, 1))
    time.sleep(random.uniform(0.05, 0.1))
    page.mouse.up()
    time.sleep(0.5)  # 等待验证结果
    return True

def solve_slider(page, timeout=5000):
    """
    尝试自动解决页面上的滑动验证码。
    返回 True 如果成功（验证消失或页面变化），否则 False。
    """
    # 常见滑动验证选择器
    selectors = [
        '.geetest_slider_button',     # 极验
        '.slider-btn',                # 自定义
        'div[class*="slider"]',       # 通用
        '.slideBtn',
        '.verify-slide-btn'
    ]

    slider_sel = None
    for sel in selectors:
        if page.query_selector(sel):
            slider_sel = sel
            break

    if not slider_sel:
        # 尝试更模糊的匹配：包含 "slide" 的 div
        elems = page.query_selector_all('div[class*="slide"]')
        for elem in elems:
            class_name = elem.get_attribute('class')
            if class_name and ('btn' in class_name or 'button' in class_name):
                slider_sel = f'div[class="{class_name}"]'
                break
    if not slider_sel:
        print("未找到任何滑动验证相关元素，可能不需要验证或页面结构未知", file=sys.stderr)
        return False

    print(f"找到滑动验证元素: {slider_sel}，尝试拖动...", file=sys.stderr)
    success = human_like_drag(page, slider_sel)
    if success:
        # 等待验证结果：验证码消失或页面跳转
        time.sleep(2)
        # 检查是否还存在滑块（若不存在则可能成功）
        if not page.query_selector(slider_sel):
            print("验证成功！", file=sys.stderr)
            return True
        # 也可能页面刷新了，重新检测
        try:
            page.wait_for_load_state('networkidle', timeout=5000)
        except:
            pass
        if not page.query_selector(slider_sel):
            print("验证成功（页面已变化）！", file=sys.stderr)
            return True
    return False

def main():
    parser = argparse.ArgumentParser(description='激活 IP 信任脚本')
    parser.add_argument('url', nargs='?', default='https://www.whquxinyong.xyz/checkout',
                        help='目标页面 URL')
    parser.add_argument('--proxy', default=None, help='代理地址，如 http://1.2.3.4:5678')
    args = parser.parse_args()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox']
        )
        context_options = {
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36',
            'viewport': {'width': 1280, 'height': 720}
        }
        if args.proxy:
            context_options['proxy'] = {'server': args.proxy}

        context = browser.new_context(**context_options)
        page = context.new_page()

        try:
            print(f"正在访问: {args.url}", file=sys.stderr)
            page.goto(args.url, wait_until='domcontentloaded', timeout=30000)

            # 检查是否包含验证码
            if '滑动验证' in page.content() or 'verify' in page.content().lower():
                print("检测到验证码，开始自动验证...", file=sys.stderr)
                if solve_slider(page):
                    # 验证成功，保存 cookies
                    cookies = context.cookies()
                    # 打印 cookies 供其他程序使用（例如 Flask）
                    import json
                    print(json.dumps([{
                        'name': c['name'],
                        'value': c['value'],
                        'domain': c.get('domain', ''),
                        'path': c.get('path', '/')
                    } for c in cookies]))
                    print("IP 已激活！", file=sys.stderr)
                else:
                    print("自动验证失败，可能需要手动处理", file=sys.stderr)
                    sys.exit(1)
            else:
                print("页面未检测到验证码，可能已经通过验证", file=sys.stderr)
                # 还是输出 cookies，方便后续使用
                import json
                cookies = context.cookies()
                print(json.dumps([{
                    'name': c['name'],
                    'value': c['value'],
                    'domain': c.get('domain', ''),
                    'path': c.get('path', '/')
                } for c in cookies]))
        except Exception as e:
            print(f"脚本运行异常: {e}", file=sys.stderr)
            sys.exit(1)
        finally:
            browser.close()

if __name__ == '__main__':
    main()