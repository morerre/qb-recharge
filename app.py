from flask import Flask, request, jsonify, render_template_string
import requests
from bs4 import BeautifulSoup
import os
import traceback

app = Flask(__name__)

BASE = "https://www.whquxinyong.xyz"
PRODUCTS = {
    "1QB": {"product_id": "197", "sku_id": "1072"},
    "5QB": {"product_id": "221", "sku_id": "1047"},
}

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

    <script>
        let payUrl = "";
        async function generateOrder() {
            const qq = document.getElementById("qq").value;
            const product = document.getElementById("product").value;
            if (!/^\d{5,}$/.test(qq)) { alert("请输入有效QQ号"); return; }
            const btn = document.querySelector("button");
            btn.disabled = true;
            document.getElementById('pay-btn').style.display = "none";
            document.getElementById('status').innerText = "正在生成订单...";
            try {
                const res = await fetch("/api/order", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ qq, product })
                });
                const data = await res.json();
                if (data.success) {
                    payUrl = data.pay_url;
                    document.getElementById('status').innerHTML = "✅ 订单生成成功！<br>点击下方按钮付款。";
                    document.getElementById('pay-btn').style.display = "block";
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
            document.getElementById('status').innerHTML += '<br>✅ 已为您打开支付页面，请查看浏览器新窗口。';
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
        s.headers.update({
            "User-Agent": "Mozilla/5.0 ... Chrome/148.0.0.0 Safari/537.36"
        })

        # 获取token
        resp = s.get(f"{BASE}/products/{config['product_id']}")
        soup = BeautifulSoup(resp.text, 'html.parser')
        token = soup.find('meta', {'name': 'csrf-token'})['content']

        # 加购
        resp = s.post(f"{BASE}/carts",
                      json={"sku_id": config['sku_id'], "quantity": 1, "buy_now": False},
                      headers={"Content-Type": "application/json", "X-CSRF-TOKEN": token,
                               "Referer": f"{BASE}/products/{config['product_id']}", "Origin": BASE})
        if resp.status_code != 200:
            raise Exception(f"加购失败，状态码: {resp.status_code}, 响应: {resp.text[:100]}")

        # 结算页刷新token
        resp = s.get(f"{BASE}/checkout")
        soup = BeautifulSoup(resp.text, 'html.parser')
        token_meta = soup.find('meta', {'name': 'csrf-token'})
        if token_meta:
            token = token_meta['content']

        # 下单
        resp = s.post(f"{BASE}/checkout/confirm",
                      json={"comment": "", "qq": qq},
                      headers={"Content-Type": "application/json", "X-CSRF-TOKEN": token,
                               "Referer": f"{BASE}/checkout", "Origin": BASE})
        if resp.status_code not in (200, 201):
            raise Exception(f"下单失败，状态码: {resp.status_code}, 响应: {resp.text[:100]}")
        order_no = resp.json()['number']

        # 获取支付链接
        resp = s.get(f"{BASE}/orders/{order_no}/NiupayPay?type=create",
                     allow_redirects=False, headers={"Referer": f"{BASE}/checkout"})
        if resp.status_code in (301, 302):
            redirect = resp.headers['Location']
            final_resp = s.get(redirect, allow_redirects=False, headers={"Referer": BASE})
            pay_url = final_resp.headers.get('Location', redirect)
        else:
            error_detail = f"支付跳转失败，状态码: {resp.status_code}, 响应: {resp.text[:200]}"
            raise Exception(error_detail)

        return jsonify(success=True, pay_url=pay_url)
    except Exception as e:
        traceback.print_exc()
        return jsonify(success=False, error=str(e))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)