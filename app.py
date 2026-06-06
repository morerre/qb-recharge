import asyncio
import re
import time as _time
import threading
from playwright.async_api import async_playwright, Browser, Playwright
from flask import Flask, request, jsonify, render_template_string
from datetime import datetime

def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")
BASE = "https://www.whquxinyong.xyz"
PRODUCTS = {
    "1QB": {"product_id": "197", "sku_id": "1072"},
    "5QB": {"product_id": "221", "sku_id": "1047"},
}

# ---------- 全局浏览器复用（单例）----------
_playwright: Playwright = None
_browser: Browser = None
_loop: asyncio.AbstractEventLoop = None
_background_thread: threading.Thread = None
_loop_ready = threading.Event()

def start_background_loop():
    global _loop
    _loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_loop)
    _loop_ready.set()
    _loop.run_forever()

async def init_browser():
    global _playwright, _browser
    if _browser is not None:
        return _browser
    _playwright = await async_playwright().start()
    _browser = await _playwright.chromium.launch(
        headless=True,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-gpu",
            "--window-size=1280,720",
            "--disable-dev-shm-usage",
            "--disable-extensions",
            "--disable-background-networking",
            "--mute-audio",
        ]
    )
    return _browser

def run_async(coro):
    if _loop is None:
        raise RuntimeError("后台事件循环未启动")
    future = asyncio.run_coroutine_threadsafe(coro, _loop)
    return future.result()

_background_thread = threading.Thread(target=start_background_loop, daemon=True)
_background_thread.start()
_loop_ready.wait(timeout=3)
if _loop is None:
    raise RuntimeError("后台事件循环启动超时")
run_async(init_browser())

# ---------- 下单核心逻辑（改进版：兼容滑块和直接跳转）----------
async def do_order(qq, product):
    if product not in PRODUCTS:
        return None, "无效面额"
    config = PRODUCTS[product]

    browser = await init_browser()
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
        viewport={"width": 1280, "height": 720}
    )
    await context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => false });
        window.chrome = { runtime: {} };
    """)
    page = await context.new_page()

    try:
        # 1. 打开商品页
        await page.goto(f"{BASE}/products/{config['product_id']}", wait_until="domcontentloaded")
        log(f"[下单] 打开商品页（面额:{product}）")

        # 2. 点击加购
        btn_selector = 'button:has-text("立即购买"), button:has-text("加入购物车"), a:has-text("立即购买")'
        try:
            await page.wait_for_selector(btn_selector, timeout=10000)
            await page.locator(btn_selector).first.click()
            log(f"[下单] 已点击加购（面额:{product}）")
        except Exception as e:
            return None, f"点击加购失败: {e}"

        await page.wait_for_timeout(500)

        # 3. 进入结算页
        await page.goto(f"{BASE}/checkout", wait_until="domcontentloaded")
        await page.wait_for_selector("input#qq, input[name='qq']", timeout=10000)

        # 4. 填写QQ并提交订单
        await page.fill("input#qq, input[name='qq']", qq)
        submit_btn = page.locator("button:has-text('确认支付'), button:has-text('提交订单')").first
        await submit_btn.click()
        log(f"[下单] QQ:{qq} 面额:{product} 已提交订单，等待支付环节...")

        # 5. 兼容两种流程：滑块 或 直接跳转
        # 先设置一个标志，记录是否已经处理过滑块
        slider_done = False
        pay_url = None

        # 同时启动两个异步任务：一个等待滑块并滑动，另一个轮询支付链接
        async def wait_and_slide():
            nonlocal slider_done
            try:
                # 只等待最多 2 秒，如果滑块出现就滑动，否则认为没有滑块
                await page.wait_for_selector(".checkout-slider-thumb", timeout=800)
                slider_done = True
                log("[下单] 检测到滑块，开始滑动...")
                slider = page.locator(".checkout-slider-thumb").first
                box = await slider.bounding_box()
                parent = slider.locator("..")
                parent_box = await parent.bounding_box()
                max_distance = parent_box['width'] - box['width'] if parent_box else 300
                start_x = box['x'] + box['width'] / 2
                start_y = box['y'] + box['height'] / 2
                await page.mouse.move(start_x, start_y)
                await page.mouse.down()
                steps = 60
                for i in range(steps + 1):
                    progress = i / steps
                    eased = 1 - (1 - progress) ** 3
                    cur_x = start_x + max_distance * eased
                    jitter = (i % 2) * 1.5
                    await page.mouse.move(cur_x, start_y + jitter, steps=1)
                    await page.wait_for_timeout(4)
                await page.mouse.up()
                log("[下单] 滑块完成")
                await page.wait_for_timeout(500)
            except Exception as e:
                # 超时或没有滑块，忽略
                log("[下单] 未出现滑块或滑块已过时，跳过")

        async def poll_pay_url():
            nonlocal pay_url
            start_time = _time.time()
            new_page = None
            def handle_new_page(p):
                nonlocal new_page
                new_page = p
            context.on("page", handle_new_page)

            while _time.time() - start_time < 15:
                # 检查当前页面URL
                cur_url = page.url
                if any(k in cur_url for k in ["payOrderId", "ztds.whqsq.xyz", "nqb.asdjwj.cn"]):
                    pay_url = cur_url
                    break
                # 检查新页面
                if new_page:
                    new_url = new_page.url
                    if any(k in new_url for k in ["payOrderId", "ztds.whqsq.xyz", "nqb.asdjwj.cn"]):
                        pay_url = new_url
                        break
                await asyncio.sleep(0.2)
            context.remove_listener("page", handle_new_page)

        # 并发执行：等待滑块 和 轮询支付链接
        await asyncio.gather(wait_and_slide(), poll_pay_url())

        # 如果轮询没有拿到支付链接，尝试从页面源码提取
        if not pay_url:
            try:
                content = await page.content()
                import re
                match = re.search(r'(https?://[^\s"\'<>]+(?:payOrderId|alipay/pay_wap_wudi)[^\s"\'<>]*)', content)
                if match:
                    pay_url = match.group(1)
                    log(f"[下单] 从页面源码提取支付链接: {pay_url}")
            except Exception as e:
                log(f"[下单] 提取支付链接失败: {e}")

        if not pay_url:
            return None, "未能获取支付链接（无滑块且未捕获跳转）"

        await context.close()
        log(f"[下单] ✅ 成功获取支付链接: {pay_url}")
        return pay_url, None

    except Exception as e:
        await context.close()
        return None, str(e)


# ---------- Flask Web 服务 ----------
app = Flask(__name__)

HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>牛牛自动下单</title>
    <style>
        body { font-family: Arial; margin: 20px; text-align: center; }
        .container { max-width: 400px; margin: auto; }
        input, select, button { padding: 10px; width: 100%; margin: 8px 0; box-sizing: border-box; font-size: 16px; }
        button { background: #007bff; color: white; border: none; cursor: pointer; }
        button:disabled { background: #ccc; }
        .pay-btn { background: #28a745; color: white; text-decoration: none; padding: 12px; border-radius: 5px; display: inline-block; width: 100%; box-sizing: border-box; }
        .loading { color: #666; font-style: italic; }
        .error { color: red; }
    </style>
</head>
<body>
<div class="container">
    <h2>牛牛自动</h2>
    <div>
        <label>QQ号:</label>
        <input type="text" id="qq" placeholder="请输入QQ号" required>
    </div>
    <div>
        <label>面额:</label>
        <select id="product">
            <option value="1QB">1QB</option>
            <option value="5QB" selected>5QB</option>
        </select>
    </div>
    <div>
        <button id="orderBtn" onclick="startOrder()">生成订单</button>
    </div>
    <div id="loading" class="loading" style="display:none;">下单中...</div>
    <div id="error" class="error"></div>
    <a id="payLink" href="#" target="_blank" class="pay-btn" style="display:none;">点击去支付</a>
</div>

<script>
async function startOrder() {
    const qq = document.getElementById('qq').value.trim();
    const product = document.getElementById('product').value;
    const btn = document.getElementById('orderBtn');
    const loading = document.getElementById('loading');
    const errorDiv = document.getElementById('error');
    const payLink = document.getElementById('payLink');

    if (!qq) {
        errorDiv.innerText = '请输入QQ号';
        return;
    }
    errorDiv.innerText = '';
    payLink.style.display = 'none';
    btn.disabled = true;
    loading.style.display = 'block';
    loading.innerText = '正在下单中';

    try {
        const formData = new FormData();
        formData.append('qq', qq);
        formData.append('product', product);

        const response = await fetch('/order', {
            method: 'POST',
            body: formData
        });
        const data = await response.json();

        if (data.status === 'success') {
            payLink.href = data.pay_url;
            payLink.style.display = 'block';
            payLink.onclick = function() {
                this.style.display = 'none';
            };
            loading.innerText = '✅ 订单生成成功！点击下方按钮支付。';
        } else {
            errorDiv.innerText = '下单失败: ' + data.message;
            loading.style.display = 'none';
        }
    } catch (err) {
        errorDiv.innerText = '网络错误: ' + err;
        loading.style.display = 'none';
    } finally {
        btn.disabled = false;
    }
}
</script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_PAGE)

@app.route('/order', methods=['POST'])
def order():
    qq = request.form.get('qq', '').strip()
    product = request.form.get('product', '').strip()
    if not qq:
        return jsonify({"status": "error", "message": "QQ号不能为空"})

    try:
        pay_url, err = run_async(do_order(qq, product))
    except Exception as e:
        return jsonify({"status": "error", "message": f"脚本异常: {str(e)}"})

    if err:
        return jsonify({"status": "error", "message": f"下单失败: {err}"})
    if not pay_url:
        return jsonify({"status": "error", "message": "未能获取支付链接"})

    match = re.search(r'payOrderId=([^&]+)', pay_url)
    order_id = match.group(1) if match else "未知"
    return jsonify({
        "status": "success",
        "order_id": order_id,
        "pay_url": pay_url
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)