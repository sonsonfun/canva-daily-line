import os
import time
import requests
import json
import base64

# 環境変数
CANVA_CLIENT_ID = os.environ["CANVA_CLIENT_ID"]
CANVA_CLIENT_SECRET = os.environ["CANVA_CLIENT_SECRET"]
CANVA_REFRESH_TOKEN = os.environ["CANVA_REFRESH_TOKEN"]
CANVA_DESIGN_ID = os.environ["CANVA_DESIGN_ID"]
LINE_CHANNEL_ACCESS_TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
LINE_USER_ID = os.environ["LINE_USER_ID"]

def refresh_canva_token():
    url = "https://api.canva.com/rest/v1/oauth/token"
    auth_str = f"{CANVA_CLIENT_ID}:{CANVA_CLIENT_SECRET}"
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
        print(f"Token Refresh Error Body: {resp.text}")
        raise Exception(f"Canva Token Refresh Failed: {resp.status_code}")
    
    tokens = resp.json()
    return tokens["access_token"], tokens.get("refresh_token")

def export_design(access_token):
    url = "https://api.canva.com/rest/v1/exports"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    
    # ★修正: 全ページ出力のため、pagesの指定を削除しました
    data = {
        "design_id": CANVA_DESIGN_ID,
        "format": {"type": "jpg", "quality": 80},
        "type": "image"
    }
    
    resp = requests.post(url, headers=headers, json=data)
    if resp.status_code != 200:
        raise Exception(f"Export Job Creation Failed: {resp.text}")
    
    job_id = resp.json()["job"]["id"]
    print(f"Export Job ID: {job_id}")

    job_url = f"{url}/{job_id}"
    while True:
        time.sleep(3)
        check_resp = requests.get(job_url, headers=headers)
        status = check_resp.json()["job"]["status"]
        
        if status == "success":
            return check_resp.json()["job"]["urls"]
        elif status == "failed":
            raise Exception("Canva Export Job Failed")
        print("Waiting for export...")

def send_line_message(image_urls):
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # ★修正: 枚数が変わっても対応できるように文言を動的に変更
    messages = [
        {
            "type": "text", 
            "text": f"本日のデザイン({len(image_urls)}枚)をお届けします！"
        }
    ]
    
    # URLのリストをループして、画像メッセージを追加
    for img_url in image_urls:
        messages.append({
            "type": "image", 
            "originalContentUrl": img_url, 
            "previewImageUrl": img_url
        })

    # LINE Messaging API制限: メッセージは最大5件まで
    # (テキスト1件 + 画像4枚までならこのまま送れます)
    data = {
        "to": LINE_USER_ID,
        "messages": messages[:5] # 万が一5枚以上あってもエラーにならないようスライスで安全策
    }
    
    resp = requests.post(url, headers=headers, json=data)
    if resp.status_code != 200:
        raise Exception(f"LINE Send Failed: {resp.text}")
    print("LINE message sent successfully!")

if __name__ == "__main__":
    try:
        print("1. Refreshing Canva Token...")
        access_token, new_refresh_token = refresh_canva_token()
        
        if new_refresh_token:
            print(f"::add-mask::{new_refresh_token}")
            with open(os.environ['GITHUB_OUTPUT'], 'a') as fh:
                print(f"new_refresh_token={new_refresh_token}", file=fh)
            print("✨ New refresh token captured.")
        
        print("2. Exporting Design...")
        img_urls = export_design(access_token)
        
        print(f"取得した画像の枚数: {len(img_urls)}")
        
        print("3. Sending to LINE...")
        send_line_message(img_urls)
        
    except Exception as e:
        print(f"Error: {e}")
        exit(1)
