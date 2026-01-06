import os
import requests
import base64
import json
import sys
import time

# 設定（Gemini関連は削除済み）
REFRESH_TOKEN = os.environ["CANVA_REFRESH_TOKEN"]
CLIENT_ID = os.environ["CANVA_CLIENT_ID"]
CLIENT_SECRET = os.environ["CANVA_CLIENT_SECRET"]
DESIGN_ID = os.environ["CANVA_DESIGN_ID"]
LINE_TOKEN = os.environ["LINE_TOKEN"]
LINE_USER_ID = os.environ["LINE_USER_ID"]

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

def export_images(access_token):
    """1枚目と2枚目をまとめて書き出す"""
    print("Canva: 画像を生成中...")
    url = "https://api.canva.com/rest/v1/exports"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    
    payload = {
        "design_id": DESIGN_ID, 
        "format": {"type": "jpg", "quality": 100}, 
        "pages": [1, 2] # 1枚目と2枚目を指定
    }
    
    resp = requests.post(url, headers=headers, json=payload)
    if resp.status_code != 200:
        print(f"Export Error: {resp.text}")
        return None
        
    job_id = resp.json().get("job", {}).get("id")
    
    for _ in range(20):
        time.sleep(3)
        check_resp = requests.get(f"{url}/{job_id}", headers=headers)
        job = check_resp.json().get("job", {})
        if job.get("status") == "success":
            return job.get("urls", [])
    return None

def main():
    # 1. トークン更新
    access_token, new_refresh_token = get_new_tokens()
    if not access_token: sys.exit(1)

    if new_refresh_token:
        with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
            f.write(f"new_refresh_token={new_refresh_token}\n")

    # 2. 画像取得
    image_urls = export_images(access_token)
    if not image_urls:
        print("画像の取得に失敗しました")
        sys.exit(1)

    line_url = "https://api.line.me/v2/bot/message/push"
    headers = {"Authorization": f"Bearer {LINE_TOKEN}", "Content-Type": "application/json"}
    
    timestamp = int(time.time())

    # 3. LINE送信（画像のみ）
    for i, url in enumerate(image_urls):
        page_num = i + 1
        
        # URLの末尾に時間を付けてキャッシュ回避
        cache_free_url = f"{url}&t={timestamp}_{page_num}"
        
        # 画像と簡単なラベルを送る
        messages = [
            {
                "type": "image", 
                "originalContentUrl": cache_free_url, 
                "previewImageUrl": cache_free_url
            },
            {
                "type": "text",
                "text": f"【{page_num}枚目】"
            }
        ]
        
        payload = {"to": LINE_USER_ID, "messages": messages}
        requests.post(line_url, headers=headers, json=payload)
        print(f"{page_num}枚目を送信しました")
        time.sleep(1)

if __name__ == "__main__":
    main()
