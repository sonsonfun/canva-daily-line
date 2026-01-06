import os
import requests
import base64
import sys
import time

# 設定
REFRESH_TOKEN = os.environ["CANVA_REFRESH_TOKEN"]
CLIENT_ID = os.environ["CANVA_CLIENT_ID"]
CLIENT_SECRET = os.environ["CANVA_CLIENT_SECRET"]
DESIGN_ID = os.environ["CANVA_DESIGN_ID"]
LINE_TOKEN = os.environ["LINE_TOKEN"]
LINE_USER_ID = os.environ["LINE_USER_ID"]

def get_new_tokens():
    """リフレッシュトークンで新しいアクセストークンを取得"""
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

def export_images(access_token):
    """Canvaの1枚目と2枚目を書き出してURLリストを取得"""
    print("Canva: 画像を生成中...")
    url = "https://api.canva.com/rest/v1/exports"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    
    # 1枚目と2枚目を指定
    payload = {
        "design_id": DESIGN_ID,
        "format": {"type": "jpg", "quality": 100},
        "pages": [1, 2] 
    }
    
    resp = requests.post(url, headers=headers, json=payload)
    if resp.status_code != 200:
        print(f"Export依頼エラー: {resp.text}")
        return None
        
    job_id = resp.json().get("job", {}).get("id")
    
    # 完了を待つ (ポーリング)
    for _ in range(20): # 最大60秒待機
        time.sleep(3)
        check_resp = requests.get(f"{url}/{job_id}", headers=headers)
        job = check_resp.json().get("job", {})
        status = job.get("status")
        
        if status == "success":
            print("Canva: 生成完了！")
            # 生成された全URLのリストを返す
            return job.get("urls", [])
        elif status == "failed":
            print("Canva: 生成失敗")
            return None
            
    print("Canva: タイムアウト")
    return None

def main():
    # 1. トークン更新
    access_token, new_refresh_token = get_new_tokens()
    if not access_token: sys.exit(1)

    # GitHub Actionsでトークンが変わった場合にログ出力（デバッグ用）
    if new_refresh_token:
        # 実際の運用ではここでSecrets更新などが理想ですが、まずはログに出すか出力変数にセット
        print("※新しいRefresh Tokenが発行されました。") 
        with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
            f.write(f"new_refresh_token={new_refresh_token}\n")

    # 2. 画像URL取得 (1枚目と2枚目)
    image_urls = export_images(access_token)
    if not image_urls:
        print("画像の取得に失敗しました。")
        sys.exit(1)

    # 3. LINE送信メッセージの作成
    line_messages = []
    for url in image_urls:
        line_messages.append({
            "type": "image",
            "originalContentUrl": url,
            "previewImageUrl": url
        })

    # LINE送信 (最大5件まで一度に送信可能)
    line_url = "https://api.line.me/v2/bot/message/push"
    headers = {"Authorization": f"Bearer {LINE_TOKEN}", "Content-Type": "application/json"}
    
    payload = {
        "to": LINE_USER_ID,
        "messages": line_messages
    }
    
    res = requests.post(line_url, headers=headers, json=payload)
    if res.status_code == 200:
        print("LINE送信成功！")
    else:
        print(f"LINE送信エラー: {res.text}")
        sys.exit(1)

if __name__ == "__main__":
    main()
