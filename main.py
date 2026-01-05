import os
import requests
import base64
import json
import sys
import time
import google.generativeai as genai
from PIL import Image
from io import BytesIO

# 設定
REFRESH_TOKEN = os.environ["CANVA_REFRESH_TOKEN"]
CLIENT_ID = os.environ["CANVA_CLIENT_ID"]
CLIENT_SECRET = os.environ["CANVA_CLIENT_SECRET"]
DESIGN_ID = os.environ["CANVA_DESIGN_ID"]
LINE_TOKEN = os.environ["LINE_TOKEN"]
LINE_USER_ID = os.environ["LINE_USER_ID"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

genai.configure(api_key=GEMINI_API_KEY)

def get_new_tokens():
    url = "https://api.canva.com/rest/v1/oauth/token"
    auth_str = f"{CLIENT_ID}:{CLIENT_SECRET}"
    b64_auth = base64.b64encode(auth_str.encode()).decode()
    headers = {"Authorization": f"Basic {b64_auth}", "Content-Type": "application/x-www-form-urlencoded"}
    data = {"grant_type": "refresh_token", "refresh_token": REFRESH_TOKEN}
    resp = requests.post(url, headers=headers, data=data)
    if resp.status_code != 200:
        print(f"★トークン更新エラー: {resp.text}")
        return None, None
    return resp.json().get("access_token"), resp.json().get("refresh_token")

def export_high_quality_image(access_token):
    """【重要】高画質画像をExport（書き出し）する"""
    print("Canva: 高画質画像を生成中...")
    url = "https://api.canva.com/rest/v1/exports"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    payload = {
        "design_id": DESIGN_ID,
        "format": {"type": "jpg", "quality": 100},
        "pages": [1]
    }
    
    resp = requests.post(url, headers=headers, json=payload)
    if resp.status_code != 200:
        print(f"Export依頼エラー: {resp.text}")
        return None
        
    job_id = resp.json().get("job", {}).get("id")
    
    # 完了を待つ
    for _ in range(15):
        time.sleep(3)
        check_resp = requests.get(f"{url}/{job_id}", headers=headers)
        job = check_resp.json().get("job", {})
        if job.get("status") == "success":
            print("Canva: 生成完了！")
            return job.get("urls", [])[0]
        elif job.get("status") == "failed":
            return None
    return None

def analyze_image_with_gemini(image_bytes):
    print("Gemini: 高画質画像を解析中...")
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        image = Image.open(BytesIO(image_bytes))
        # ↓エクセル用にプロンプトを具体化
        prompt = """
        画像はエクセルの表です。
        1. 表に含まれる数値を正確に読み取ってください。
        2. 各項目ごとに、LINEで見やすいように箇条書きにまとめてください。
        3. 最後に簡単な一言要約を添えてください。
        """
        response = model.generate_content([prompt, image])
        return response.text
    except Exception as e:
        print(f"Geminiエラー: {e}")
        return "読み取り失敗"

def main():
    access_token, new_refresh_token = get_new_tokens()
    if not access_token: sys.exit(1)

    if new_refresh_token:
        with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
            f.write(f"new_refresh_token={new_refresh_token}\n")

    # サムネイルではなく高画質Exportを使用
    image_url = export_high_quality_image(access_token)
    if not image_url:
        print("高画質画像の取得に失敗しました。")
        sys.exit(1)

    img_resp = requests.get(image_url)
    text_msg = analyze_image_with_gemini(img_resp.content)
    
    # LINE送信
    line_url = "https://api.line.me/v2/bot/message/push"
    headers = {"Authorization": f"Bearer {LINE_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "to": LINE_USER_ID,
        "messages": [
            {"type": "image", "originalContentUrl": image_url, "previewImageUrl": image_url},
            {"type": "text", "text": text_msg}
        ]
    }
    requests.post(line_url, headers=headers, json=payload)
    print("送信成功！")

if __name__ == "__main__":
    main()
