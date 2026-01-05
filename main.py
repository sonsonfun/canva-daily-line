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
        return None, None
    return resp.json().get("access_token"), resp.json().get("refresh_token")

def export_high_quality_image(access_token):
    """2枚目（Page 2）を書き出す設定"""
    url = "https://api.canva.com/rest/v1/exports"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    
    # 構文エラーを修正しました
    payload = {
        "design_id": DESIGN_ID, 
        "format": {"type": "jpg", "quality": 100}, 
        "pages": [2]
    }
    
    resp = requests.post(url, headers=headers, json=payload)
    if resp.status_code != 200:
        print(f"Export失敗: {resp.text}")
        return None
        
    job_id = resp.json().get("job", {}).get("id")
    
    for _ in range(15):
        time.sleep(3)
        check_resp = requests.get(f"{url}/{job_id}", headers=headers)
        job = check_resp.json().get("job", {})
        if job.get("status") == "success":
            return job.get("urls", [])[0]
    return None

def analyze_image_with_gemini(image_bytes):
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        image = Image.open(BytesIO(image_bytes))
        prompt = """
        画像はエクセルの表です。項目と数値を正確に読み取って整理してください。
        もし内容が読み取れない場合は「解析不可」とだけ答えてください。
        """
        response = model.generate_content([prompt, image])
        result = response.text.strip()
        if "解析不可" in result or not result:
            return None
        return result
    except Exception:
        return None

def main():
    access_token, new_refresh_token = get_new_tokens()
    if not access_token: sys.exit(1)

    if new_refresh_token:
        with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
            f.write(f"new_refresh_token={new_refresh_token}\n")

    image_url = export_high_quality_image(access_token)
    if not image_url: sys.exit(1)

    img_resp = requests.get(image_url)
    text_msg = analyze_image_with_gemini(img_resp.content)
    
    line_url = "https://api.line.me/v2/bot/message/push"
    headers = {"Authorization": f"Bearer {LINE_TOKEN}", "Content-Type": "application/json"}
    
    # 画像送信（URLの末尾にダミーの数字を足してキャッシュを回避）
    timestamp = int(time.time())
    cache_free_url = f"{image_url}&t={timestamp}"
    
    messages = [{"type": "image", "originalContentUrl": cache_free_url, "previewImageUrl": cache_free_url}]
    if text_msg:
        messages.append({"type": "text", "text": text_msg})
    
    payload = {"to": LINE_USER_ID, "messages": messages}
    requests.post(line_url, headers=headers, json=payload)

if __name__ == "__main__":
    main()
