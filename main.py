import os
import time
import requests
import json

# 環境変数から設定を読み込み
CANVA_CLIENT_ID = os.environ["CANVA_CLIENT_ID"]
CANVA_CLIENT_SECRET = os.environ["CANVA_CLIENT_SECRET"]
CANVA_REFRESH_TOKEN = os.environ["CANVA_REFRESH_TOKEN"]
CANVA_DESIGN_ID = os.environ["CANVA_DESIGN_ID"]
LINE_CHANNEL_ACCESS_TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
LINE_USER_ID = os.environ["LINE_USER_ID"]

def refresh_canva_token():
    """Canvaのアクセストークンを更新する"""
    url = "https://api.canva.com/rest/v1/oauth/token"
    auth_str = f"{CANVA_CLIENT_ID}:{CANVA_CLIENT_SECRET}"
    import base64
    b64_auth = base64.b64encode(auth_str.encode()).decode()

    headers = {
        "Authorization": f"Basic {b64_auth}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "grant_type": "refresh_token",
        "refresh_token": CANVA_REFRESH_TOKEN
    }
    
    resp = requests.post(url, headers=headers, data=data)
    if resp.status_code != 200:
        raise Exception(f"Canva Token Refresh Failed: {resp.text}")
    return resp.json()["access_token"]

def export_design(access_token):
    """デザインをJPG画像としてエクスポートし、URLを取得する"""
    # 1. エクスポートジョブの作成
    url = "https://api.canva.com/rest/v1/exports"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    data = {
        "design_id": CANVA_DESIGN_ID,
        "format": {"type": "jpg", "quality": 80}, # JPGでエクスポート
        "type": "image"
    }
    
    resp = requests.post(url, headers=headers, json=data)
    if resp.status_code != 200:
        raise Exception(f"Export Job Creation Failed: {resp.text}")
    
    job_id = resp.json()["job"]["id"]
    print(f"Export Job ID: {job_id}")

    # 2. ジョブ完了までポーリング（待機）
    job_url = f"{url}/{job_id}"
    while True:
        time.sleep(3) # 3秒待機
        check_resp = requests.get(job_url, headers=headers)
        status = check_resp.json()["job"]["status"]
        
        if status == "success":
            # 完了したら画像のURLを返す
            return check_resp.json()["job"]["urls"][0]
        elif status == "failed":
            raise Exception("Canva Export Job Failed")
        print("Waiting for export...")

def send_line_message(image_url):
    """LINEに画像を送信する"""
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # 画像メッセージのペイロード
    data = {
        "to": LINE_USER_ID,
        "messages": [
            {
                "type": "text",
                "text": "本日のデザインをお届けします！"
            },
            {
                "type": "image",
                "originalContentUrl": image_url,
                "previewImageUrl": image_url
            }
        ]
    }
    
    resp = requests.post(url, headers=headers, json=data)
    if resp.status_code != 200:
        raise Exception(f"LINE Send Failed: {resp.text}")
    print("LINE message sent successfully!")

if __name__ == "__main__":
    try:
        print("1. Refreshing Canva Token...")
        token = refresh_canva_token()
        
        print("2. Exporting Design...")
        img_url = export_design(token)
        print(f"Image URL: {img_url}")
        
        print("3. Sending to LINE...")
        send_line_message(img_url)
        
    except Exception as e:
        print(f"Error: {e}")
        # エラー時もLINEに通知したい場合はここにエラー通知処理を追加
        exit(1)
