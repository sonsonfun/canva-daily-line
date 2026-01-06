import os
import requests
import base64
import json
import sys
import time
# AI関連のライブラリは削除しました

# 設定
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
    if resp.status_code != 200: return None, None
    return resp.json().get("access_token"), resp.json().get("refresh_token")

def export_all_pages(access_token):
    """1枚目と2枚目を両方書き出す"""
    url = "https://api.canva.com/rest/v1/exports"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    
    # 強制的に1と2の両方を取得
    payload = {
        "design_id": DESIGN_ID, 
        "format": {"type": "jpg", "quality": 100}, 
        "pages": [1, 2]
    }
    
    resp = requests.post(url, headers=headers, json=payload)
    if resp.status_code != 200: return None
    job_id = resp.json().get("job", {}).get("id")
    
    for _ in range(15):
        time.sleep(3)
        check_resp = requests.get(f"{url}/{job_id}", headers=headers)
        job = check_resp.json().get("job", {})
        if job.get("status") == "success":
            return job.get("urls", [])
    return None

def main():
    access_token, new_refresh_token = get_new_tokens()
    if not access_token: sys.exit(1)

    if new_refresh_token:
        with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
            f.write(f"new_refresh_token={new_refresh_token}\n")

    # 画像URLリストを取得
    urls = export_all_pages(access_token)
    if not urls: sys.exit(1)

    line_url = "https://api.line.me/v2/bot/message/push"
    headers = {"Authorization": f"Bearer {LINE_TOKEN}", "Content-Type": "application/json"}
    
    # タイムスタンプでキャッシュ回避
    ts = int(time.time())

    # 1ページ目と2ページ目を、ラベル付きで送信
    messages = []
    
    # APIが思う「1枚目」
    url1 = f"{urls[0]}&t={ts}_1"
    messages.append({"type": "text", "text": "👇 APIが認識している【1ページ目】"})
    messages.append({"type": "image", "originalContentUrl": url1, "previewImageUrl": url1})

    # APIが思う「2枚目」
    if len(urls) > 1:
        url2 = f"{urls[1]}&t={ts}_2"
        messages.append({"type": "text", "text": "👇 APIが認識している【2ページ目】"})
        messages.append({"type": "image", "originalContentUrl": url2, "previewImageUrl": url2})

    payload = {"to": LINE_USER_ID, "messages": messages}
    requests.post(line_url, headers=headers, json=payload)

if __name__ == "__main__":
    main()
