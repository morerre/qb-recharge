import asyncio
import re
import time as _time
from urllib.parse import unquote
from playwright.async_api import async_playwright
from flask import Flask, request, jsonify, render_template_string

BASE = "https://www.whquxinyong.xyz"
PRODUCTS = {
    "1QB": {"product_id": "197", "sku_id": "1072"},
    "5QB": {"product_id": "221", "sku_id": "1047"},
}

async def do_order(qq, product):
    if product not in PRODUCTS:
        return None, "无效面额"
    config = PRODUCTS[product]

    async with async_playwright() as p:
        browser = await p.chromium.launch(
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
            # 1. 打开商品页（仅等DOM加载）
            await page.goto(f"{BASE}/products/{config['product_id']}", wait_until="domcontentloaded")

            # 2. 点击加购按钮（兼容“立即购买”和“加入购物车”）
            btn_selector = 'button:has-text("立即购买"), button:has-text("加入购物车"), a:has-text("立即购买")'
            try:
                await page.wait_for_selector(btn_selector, timeout=10000)
                await page.locator(btn_selector).first.click()
                print(f"[下单] 已点击加购（面额:{product}）")
            except Exception as e:
                return None, f"点击加购按钮失败: {e}"

            # 等待购物车更新（等待一个提示或简短固定时间，这里用500ms，比1000ms快一半）
            await page.wait_for_timeout(500)

            # 3. 进入结算页
            await page.goto(f"{BASE}/checkout", wait_until="domcontentloaded")
            await page.wait_for_selector("input#qq, input[name='qq']", timeout=10000)

            # 4. 填写QQ并提交
            await page.fill("input#qq, input[name='qq']", qq)
            submit_btn = page.locator("button:has-text('确认支付'), button:has-text('提交订单')").first
            await submit_btn.click()
            print(f"[下单] QQ:{qq} 面额:{product} 已提交，等待滑块...")
            await page.wait_for_selector(".checkout-slider-thumb", timeout=15000)

            # 5. 滑块（加快滑动速度）
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
                await page.wait_for_timeout(4)   # 6 → 4ms，总滑动约160ms
            await page.mouse.up()
            print("[下单] 滑块完成")
            await page.wait_for_timeout(200)    # 500 → 200ms

            # 6. 获取支付链接（轮询间隔减半）
            start_time = _time.time()
            pay_url = None
            new_page = None
            async def handle_new_page(p):
                nonlocal new_page
                new_page = p
            context.on("page", handle_new_page)

            while _time.time() - start_time < 15:
                cur_url = page.url
                if "payOrderId" in cur_url or "ztds.whqsq.xyz" in cur_url:
                    pay_url = cur_url
                    break
                if new_page:
                    new_url = new_page.url
                    if "payOrderId" in new_url or "ztds.whqsq.xyz" in new_url:
                        pay_url = new_url
                        break
                await asyncio.sleep(0.1)    # 0.15 → 0.1秒
            context.remove_listener("page", handle_new_page)

            if not pay_url:
                try:
                    el = page.locator("a[href*='payOrderId'], a[href*='ztds.whqsq.xyz']").first
                    pay_url = await el.get_attribute("href")
                except:
                    pass

            await browser.close()
            return pay_url, None
        except Exception as e:
            await browser.close()
            return None, str(e)
    if product not in PRODUCTS:
        return None, "无效面额"
    config = PRODUCTS[product]

    async with async_playwright() as p:
        browser = await p.chromium.launch(
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
            await page.goto(f"{BASE}/products/{config['product_id']}", wait_until="networkidle")

            # 2. 点击加购按钮（兼容“立即购买”和“加入购物车”）
            btn_selector = 'button:has-text("立即购买"), button:has-text("加入购物车"), a:has-text("立即购买")'
            try:
                await page.wait_for_selector(btn_selector, timeout=10000)
                await page.locator(btn_selector).first.click()
                print(f"[下单] 已点击加购按钮（面额:{product}）")
            except Exception as e:
                return None, f"点击加购按钮失败: {e}"
            # 等待购物车更新
            await page.wait_for_timeout(1000)

            # 3. 进入结算页
            await page.goto(f"{BASE}/checkout", wait_until="networkidle")
            await page.wait_for_selector("input#qq, input[name='qq']", timeout=10000)

            # 4. 填写QQ并提交
            await page.fill("input#qq, input[name='qq']", qq)
            submit_btn = page.locator("button:has-text('确认支付'), button:has-text('提交订单')").first
            await submit_btn.click()
            print(f"[下单] QQ:{qq} 面额:{product} 已提交，等待滑块...")
            await page.wait_for_selector(".checkout-slider-thumb", timeout=15000)

            # 5. 滑块
            slider = page.locator(".checkout-slider-thumb").first
            box = await slider.bounding_box()
            parent = slider.locator("..")
            parent_box = await parent.bounding_box()
            max_distance = parent_box['width'] - box['width'] if parent_box else 300
            start_x = box['x'] + box['width'] / 2
            start_y = box['y'] + box['height'] / 2
            await page.mouse.move(start_x, start_y)
            await page.mouse.down()
            steps = 40
            for i in range(steps + 1):
                progress = i / steps
                eased = 1 - (1 - progress) ** 3
                cur_x = start_x + max_distance * eased
                jitter = (i % 2) * 1.5
                await page.mouse.move(cur_x, start_y + jitter, steps=1)
                await page.wait_for_timeout(6)
            await page.mouse.up()
            print("[下单] 滑块完成")
            await page.wait_for_timeout(500)

            # 6. 获取支付链接（轮询加速）
            start_time = _time.time()
            pay_url = None
            new_page = None
            async def handle_new_page(p):
                nonlocal new_page
                new_page = p
            context.on("page", handle_new_page)

            while _time.time() - start_time < 15:
                cur_url = page.url
                if "payOrderId" in cur_url or "ztds.whqsq.xyz" in cur_url:
                    pay_url = cur_url
                    break
                if new_page:
                    new_url = new_page.url
                    if "payOrderId" in new_url or "ztds.whqsq.xyz" in new_url:
                        pay_url = new_url
                        break
                await asyncio.sleep(0.15)
            context.remove_listener("page", handle_new_page)

            if not pay_url:
                try:
                    el = page.locator("a[href*='payOrderId'], a[href*='ztds.whqsq.xyz']").first
                    pay_url = await el.get_attribute("href")
                except:
                    pass

            await browser.close()
            return pay_url, None
        except Exception as e:
            await browser.close()
            return None, str(e)

# ---------- Flask 部分保持不变 ----------
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
        pay_url, err = asyncio.run(do_order(qq, product))
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
    app.run(host='0.0.0.0', port=5000, debug=True)