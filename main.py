import os
import requests
import base64
import json
import sys

# ==================================================
# GitHub Actionsの「Secrets」から設定を読み込むエリア
# ==================================================
# ※ここは書き換えないでください
REFRESH_TOKEN = os.environ["CANVA_REFRESH_TOKEN"]
CLIENT_ID = os.environ["CANVA_CLIENT_ID"]
CLIENT_SECRET = os.environ["CANVA_CLIENT_SECRET"]
DESIGN_ID = os.environ["CANVA_DESIGN_ID"]
LINE_TOKEN = os.environ["LINE_TOKEN"]
LINE_USER_ID = os.environ["LINE_USER_ID"]
# ==================================================

def get_new_access_token():
    """リフレッシュトークンを使って、新しいアクセストークンを発行する"""
    url = "https://api.canva.com/rest/v1/oauth/token"
    
    # IDとSecretをBase64でエンコードして認証ヘッダーを作る
    auth_str = f"{CLIENT_ID}:{CLIENT_SECRET}"
    b64_auth = base64.b64encode(auth_str.encode()).decode()
    
    headers = {
        "Authorization": f"Basic {b64_auth}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    data = {
        "grant_type": "refresh_token",
        "refresh_token": REFRESH_TOKEN
    }
    
    print("Canva: トークンを更新中...")
    resp = requests.post(url, headers=headers, data=data)
    
    if resp.status_code != 200:
        print(f"★トークン更新エラー: {resp.status_code}")
        print(resp.text)
        return None
        
    return resp.json().get("access_token")

def main():
    # 1. 新しい鍵（アクセストークン）をゲット
    access_token = get_new_access_token()
    if not access_token:
        sys.exit(1)

    # 2. デザイン情報（サムネイル）を取得
    print("Canva: デザインを取得中...")
    url = f"https://api.canva.com/rest/v1/designs/{DESIGN_ID}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        print("★Canvaデータ取得エラー")
        print(resp.text)
        sys.exit(1)

    data = resp.json()
    # サムネイル画像のURLを取り出す
    thumbnail_url = data.get("design", {}).get("thumbnail", {}).get("url")

    if not thumbnail_url:
        print("エラー: サムネイルが見つかりませんでした")
        sys.exit(1)
        
    print("Canva: 画像取得成功！")

    # 3. LINEに送信
    print("LINE: 送信中...")
    line_url = "https://api.line.me/v2/bot/message/push"
    line_headers = {
        "Authorization": f"Bearer {LINE_TOKEN}",
        "Content-Type": "application/json"
    }
    line_payload = {
        "to": LINE_USER_ID,
        "messages": [{
            "type": "image",
            "originalContentUrl": thumbnail_url,
            "previewImageUrl": thumbnail_url
        }]
    }
    
    line_resp = requests.post(line_url, headers=line_headers, json=line_payload)
    if line_resp.status_code == 200:
        print("LINE: 送信成功！")
    else:
        print(f"LINE送信エラー: {line_resp.text}")

if __name__ == "__main__":
    main()