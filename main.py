import os
import requests
import base64
import time
import json

def main():
    # --- 1. 環境変数の取得 ---
    CANVA_CLIENT_ID = os.environ.get("CANVA_CLIENT_ID")
    CANVA_CLIENT_SECRET = os.environ.get("CANVA_CLIENT_SECRET")
    CANVA_REFRESH_TOKEN = os.environ.get("CANVA_REFRESH_TOKEN")
    CANVA_DESIGN_ID = os.environ.get("CANVA_DESIGN_ID")
    LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")

    if not all([CANVA_CLIENT_ID, CANVA_CLIENT_SECRET, CANVA_REFRESH_TOKEN, LINE_CHANNEL_ACCESS_TOKEN, CANVA_DESIGN_ID]):
        print("Error: 必要な環境変数が設定されていません。")
        return

    # --- 2. Canva アクセストークンの更新 ---
    print("Canvaトークンを更新中...")
    auth_str = f"{CANVA_CLIENT_ID}:{CANVA_CLIENT_SECRET}"
    b64_auth_str = base64.b64encode(auth_str.encode()).decode()

    token_url = "https://api.canva.com/rest/v1/oauth/token"
    token_headers = {
        "Authorization": f"Basic {b64_auth_str}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    token_data = {
        "grant_type": "refresh_token",
        "refresh_token": CANVA_REFRESH_TOKEN
    }

    token_resp = requests.post(token_url, headers=token_headers, data=token_data)
    
    if token_resp.status_code != 200:
        print(f"【エラー】トークン更新失敗: {token_resp.status_code} {token_resp.text}")
        exit(1)

    tokens = token_resp.json()
    access_token = tokens.get("access_token")
    new_refresh_token = tokens.get("refresh_token")

    # 新しいリフレッシュトークンをGitHub Actions出力へ保存
    if new_refresh_token and "GITHUB_OUTPUT" in os.environ:
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"new_refresh_token={new_refresh_token}\n")

    # --- 3. デザインを画像(JPG)としてエクスポート (全ページ取得のため) ---
    print(f"デザイン(ID: {CANVA_DESIGN_ID}) の書き出しを開始します...")
    
    export_url = "https://api.canva.com/rest/v1/exports"
    export_headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    # JPG形式で書き出し（全ページ）
    export_data = {
        "design_id": CANVA_DESIGN_ID,
        "format": {
            "type": "jpg",
            "quality": 100
        }
    }

    # エクスポートジョブの作成
    job_resp = requests.post(export_url, headers=export_headers, json=export_data)
    
    if job_resp.status_code != 200:
        print(f"【エラー】書き出し開始失敗: {job_resp.status_code} {job_resp.text}")
        return

    job_id = job_resp.json().get("job", {}).get("id")
    print(f"書き出しジョブID: {job_id}")

    # --- 4. 書き出し完了まで待機 (ポーリング) ---
    image_urls = []
    
    for _ in range(20): # 最大20回確認 (約40-60秒待機)
        time.sleep(3) # 3秒待つ
        
        status_url = f"https://api.canva.com/rest/v1/exports/{job_id}"
        status_resp = requests.get(status_url, headers=export_headers)
        
        if status_resp.status_code == 200:
            job_status = status_resp.json().get("job", {})
            state = job_status.get("status")
            
            if state == "success":
                print("書き出し完了！")
                image_urls = job_status.get("urls", [])
                break
            elif state == "failed":
                print("書き出しに失敗しました。")
                return
        else:
            print(f"ステータス確認エラー: {status_resp.status_code}")
    
    if not image_urls:
        print("画像の取得に失敗、またはタイムアウトしました。")
        return

    print(f"取得した画像枚数: {len(image_urls)}枚")

    # --- 5. LINEへ送信 (Broadcast) ---
    print("LINEへ送信を開始します...")
    
    # 送信用のメッセージリストを作成
    messages = []

    # 1つ目のフキダシ: テキスト
    messages.append({
        "type": "text",
        "text": f"本日のデザイン({len(image_urls)}枚)をお届けします！"
    })

    # 2つ目以降のフキダシ: 画像 (最大4枚まで追加可能 ※LINE仕様で合計5フキダシまで)
    # 枚数が多い場合を考慮して、最初の4枚までを画像として添付します
    for img_url in image_urls[:4]:
        messages.append({
            "type": "image",
            "originalContentUrl": img_url,
            "previewImageUrl": img_url
        })

    line_url = "https://api.line.me/v2/bot/message/broadcast"
    line_headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"
    }
    line_payload = {
        "messages": messages
    }

    line_resp = requests.post(line_url, headers=line_headers, json=line_payload)

    if line_resp.status_code == 200:
        print("LINE送信成功！")
    else:
        print(f"LINE送信失敗: {line_resp.status_code} {line_resp.text}")
        # もし画像枚数が多すぎてエラーになった場合の予備処理（テキストだけ送るなど）を入れることも可能です

if __name__ == "__main__":
    main()
