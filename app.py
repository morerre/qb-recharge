from flask import Flask, request, jsonify, render_template_string
import requests
from bs4 import BeautifulSoup
import os
import traceback
import time
import random

app = Flask(__name__)

BASE = "https://www.whquxinyong.xyz"
PRODUCTS = {
    "1QB": {"product_id": "197", "sku_id": "1072"},
    "5QB": {"product_id": "221", "sku_id": "1047"},
}

# ================= 动态代理配置 =================
PROXY_API_URL = "http://v2.api.juliangip.com/postpay/getips?num=1&pt=1&result_type=text&split=1&trade_no=6538645717948532&sign=8e14bcedbdd1c50743cc5cda8dfb9520"

# 缓存最近一次代理，避免频繁调用API（30秒有效期）
_last_proxy = None
_last_proxy_time = 0

def get_proxy():
    """获取一个动态代理 IP，返回 requests 格式的代理字典，失败返回 None"""
    global _last_proxy, _last_proxy_time
    # 如果代理缓存未过期（30秒内），直接使用
    if _last_proxy and time.time() - _last_proxy_time < 25:
        return _last_proxy
    try:
        resp = requests.get(PROXY_API_URL, timeout=3)
        ip = resp.text.strip()
        if ip and ':' in ip:
            proxy_url = f"http://{ip}"
            _last_proxy = {"http": proxy_url, "https": proxy_url}
            _last_proxy_time = time.time()
            return _last_proxy
    except:
        pass
    # 失败返回 None，后续逻辑会降级
    return None

# 是否对所有请求使用代理（默认 False，只对支付跳转用代理）
USE_PROXY_FOR_ALL = False
# ============================================

HTML_PAGE = '''
<!DOCTYPE html>
<html>
<head>
    <link rel="icon" type="image/x-icon" href="/static/favicon.ico">
    <title>自动助手</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: sans-serif; max-width: 400px; margin: 40px auto; padding: 20px; }
        input, select, button {
            width: 100%;
            padding: 10px;
            margin: 8px 0;
            font-size: 16px;
            box-sizing: border-box;
            border: 1px solid #ccc;
        }
        button { background: #1677ff; color: white; border: none; border-radius: 6px; cursor: pointer; }
        button:disabled { background: #aaa; }
        #status { margin-top: 15px; padding: 10px; background: #f0f0f0; border-radius: 6px; }
        #pay-btn { background: #52c41a; display: none; }
        #manual-btn { background: #fa8c16; display: none; }
    </style>
</head>
<body>
    <h2>Q币充值助手</h2>
    <label>QQ号码：</label>
    <input type="text" id="qq" placeholder="请输入QQ号">
    <label>面额：</label>
    <select id="product">
        <option value="5QB">5QB</option>
        <option value="1QB">1QB</option>
    </select>
    <button onclick="generateOrder()">开始生成订单</button>
    <div id="status">等待操作...</div>
    <button id="pay-btn" onclick="openPayment()">打开支付宝付款</button>
    <button id="manual-btn" onclick="openManualPayment()">手动完成支付</button>

    <script>
        let payUrl = "";
        let manualUrl = "";
        async function generateOrder() {
            const qq = document.getElementById("qq").value;
            const product = document.getElementById("product").value;
            if (!/^\d{5,}$/.test(qq)) { alert("请输入有效QQ号"); return; }
            const btn = document.querySelector("button");
            btn.disabled = true;
            document.getElementById('pay-btn').style.display = "none";
            document.getElementById('manual-btn').style.display = "none";
            document.getElementById('status').innerText = "正在生成订单...";
            try {
                const res = await fetch("/api/order", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ qq, product })
                });
                const data = await res.json();
                if (data.success) {
                    if (data.pay_url) {
                        payUrl = data.pay_url;
                        document.getElementById('status').innerHTML = "✅ 订单生成成功！<br>点击下方按钮付款。";
                        document.getElementById('pay-btn').style.display = "block";
                    } else if (data.manual_url) {
                        manualUrl = data.manual_url;
                        document.getElementById('status').innerHTML = "✅ 订单已生成，<br>但需手动完成验证。<br>请点击下方按钮，在新窗口中完成滑动验证。";
                        document.getElementById('manual-btn').style.display = "block";
                    }
                } else {
                    document.getElementById('status').innerText = "❌ 失败：" + data.error;
                }
            } catch (e) {
                document.getElementById('status').innerText = "❌ 网络错误";
            }
            btn.disabled = false;
        }
        function openPayment() {
            if (!payUrl) return;
            window.open(payUrl, "_blank");
            document.getElementById('pay-btn').style.display = "none";
            document.getElementById('status').innerHTML += '<br>✅ 已为您打开支付宝页面，请查看新窗口。';
        }
        function openManualPayment() {
            if (!manualUrl) return;
            window.open(manualUrl, "_blank");
            document.getElementById('manual-btn').style.display = "none";
            document.getElementById('status').innerHTML += '<br>🔔 已打开验证页面，请在新窗口中完成滑动验证后自动付款。';
        }
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML_PAGE)

@app.route('/api/order', methods=['POST'])
def create_order():
    data = request.get_json()
    qq = data.get('qq', '').strip()
    product = data.get('product', '5QB')
    if not qq or not qq.isdigit():
        return jsonify(success=False, error='QQ号格式错误')

    config = PRODUCTS.get(product)
    if not config:
        return jsonify(success=False, error='不支持的面额')

    try:
        s = requests.Session()
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        ]
        s.headers.update({
            "User-Agent": random.choice(user_agents),
            "Accept-Language": "zh-CN,zh;q=0.9",
        })

        # 决定是否对所有请求使用代理（全局开关）
        base_proxy = get_proxy() if USE_PROXY_FOR_ALL else None

        # 获取 token
        resp = s.get(f"{BASE}/products/{config['product_id']}", proxies=base_proxy)
        soup = BeautifulSoup(resp.text, 'html.parser')
        token = soup.find('meta', {'name': 'csrf-token'})['content']

        # 加购
        time.sleep(random.uniform(1, 2))
        resp = s.post(f"{BASE}/carts",
                      json={"sku_id": config['sku_id'], "quantity": 1, "buy_now": False},
                      headers={"Content-Type": "application/json", "X-CSRF-TOKEN": token,
                               "Referer": f"{BASE}/products/{config['product_id']}", "Origin": BASE},
                      proxies=base_proxy)
        if resp.status_code != 200:
            raise Exception(f"加购失败，状态码: {resp.status_code}")

        # 结算页刷新 token
        time.sleep(random.uniform(0.5, 1.5))
        resp = s.get(f"{BASE}/checkout", proxies=base_proxy)
        soup = BeautifulSoup(resp.text, 'html.parser')
        token_meta = soup.find('meta', {'name': 'csrf-token'})
        if token_meta:
            token = token_meta['content']

        # 下单
        time.sleep(random.uniform(1, 2))
        resp = s.post(f"{BASE}/checkout/confirm",
                      json={"comment": "", "qq": qq},
                      headers={"Content-Type": "application/json", "X-CSRF-TOKEN": token,
                               "Referer": f"{BASE}/checkout", "Origin": BASE},
                      proxies=base_proxy)
        if resp.status_code not in (200, 201):
            raise Exception(f"下单失败，状态码: {resp.status_code}")
        order_no = resp.json()['number']

        # 获取支付链接（这里专门用新代理）
        pay_proxy = get_proxy()  # 每次支付跳转都尝试获取新代理
        resp = s.get(f"{BASE}/orders/{order_no}/NiupayPay?type=create",
                     allow_redirects=False, headers={"Referer": f"{BASE}/checkout"},
                     proxies=pay_proxy)
        if resp.status_code in (301, 302):
            redirect = resp.headers['Location']
            final_resp = s.get(redirect, allow_redirects=False, headers={"Referer": BASE}, proxies=pay_proxy)
            pay_url = final_resp.headers.get('Location', redirect)
            return jsonify(success=True, pay_url=pay_url)
        else:
            # 代理也失败，回退手动模式
            manual_url = f"{BASE}/orders/{order_no}/NiupayPay?type=create"
            return jsonify(success=True, manual_url=manual_url)

    except Exception as e:
        traceback.print_exc()
        return jsonify(success=False, error=str(e))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)