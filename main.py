import os
import requests
import base64
import json
import sys
import time

# 設定
REFRESH_TOKEN = os.environ.get("CANVA_REFRESH_TOKEN")
CLIENT_ID = os.environ.get("CANVA_CLIENT_ID")
CLIENT_SECRET = os.environ.get("CANVA_CLIENT_SECRET")
DESIGN_ID = os.environ.get("CANVA_DESIGN_ID")
LINE_TOKEN = os.environ.get("LINE_TOKEN")
LINE_USER_ID = os.environ.get("LINE_USER_ID")

def get_new_tokens():
    print("認証トークンを更新中...")
    url = "https://api.canva.com/rest/v1/oauth/token"
    auth_str = f"{CLIENT_ID}:{CLIENT_SECRET}"
    b64_auth = base64.b64encode(auth_str.encode()).decode()
    headers = {"Authorization": f"Basic {b64_auth}", "Content-Type": "application/x-www-form-urlencoded"}
    data = {"grant_type": "refresh_token", "refresh_token": REFRESH_TOKEN}
    
    try:
        resp = requests.post(url, headers=headers, data=data)
        if resp.status_code != 200:
            print(f"【エラー】トークン更新失敗: {resp.status_code} {resp.text}")
            return None, None
        return resp.json().get("access_token"), resp.json().get("refresh_token")
    except Exception as e:
        print(f"【エラー】接続エラー: {e}")
        return None, None

def export_images(access_token):
    print(f"Canvaから画像を書き出し中... (ID: {DESIGN_ID})")
    url = "https://api.canva.com/rest/v1/exports"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    
    payload = {
        "design_id": DESIGN_ID, 
        "format": {"type": "jpg", "quality": 100}, 
        "pages": [1, 2]
    }
    
    resp = requests.post(url, headers=headers, json=payload)
    if resp.status_code != 200:
        print(f"【エラー】書き出しリクエスト失敗: {resp.status_code}")
        print(f"詳細: {resp.text}")
        return None
        
    job_id = resp.json().get("job", {}).get("id")
    print(f"ジョブID取得成功: {job_id}. 完了を待機中...")
    
    for i in range(20):
        time.sleep(3)
        check_resp = requests.get(f"{url}/{job_id}", headers=headers)
        job = check_resp.json().get("job", {})
        status = job.get("status")
        
        if status == "success":
            print("書き出し成功！")
            return job.get("urls", [])
        elif status == "failed":
            print(f"【エラー】Canva側で処理失敗: {job.get('error')}")
            return None
            
    print("【エラー】タイムアウトしました")
    return None

def main():
    if not REFRESH_TOKEN or not DESIGN_ID:
        print("【エラー】GitHub Secretsの設定が空です！DESIGN_IDなどを確認してください。")
        sys.exit(1)

    access_token, new_refresh_token = get_new_tokens()
    if not access_token: sys.exit(1)

    if new_refresh_token:
        with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
            f.write(f"new_refresh_token={new_refresh_token}\n")

    image_urls = export_images(access_token)
    if not image_urls:
        print("画像の取得に失敗したため、終了します。")
        sys.exit(1)

    print(f"取得した画像URL数: {len(image_urls)}")
    
    line_url = "https://api.line.me/v2/bot/message/push"
    headers = {"Authorization": f"Bearer {LINE_TOKEN}", "Content-Type": "application/json"}
    timestamp = int(time.time())

    # LINE送信
    for i, url in enumerate(image_urls):
        page_num = i + 1
        cache_free_url = f"{url}&t={timestamp}_{page_num}"
        
        messages = [
            {"type": "image", "originalContentUrl": cache_free_url, "previewImageUrl": cache_free_url},
            {"type": "text", "text": f"【{page_num}枚目】"}
        ]
        
        res = requests.post(line_url, headers=headers, json={"to": LINE_USER_ID, "messages": messages})
        if res.status_code == 200:
            print(f"{page_num}枚目を送信しました")
        else:
            print(f"【エラー】LINE送信失敗: {res.text}")
        time.sleep(1)

if __name__ == "__main__":
    main()
