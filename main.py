import os
import requests
import base64
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

    # --- 3. Canvaから実際のデザイン情報を取得 ---
    print(f"デザイン情報を取得中 (ID: {CANVA_DESIGN_ID})...")
    
    design_url = f"https://api.canva.com/rest/v1/designs/{CANVA_DESIGN_ID}"
    design_headers = {
        "Authorization": f"Bearer {access_token}"
    }
    
    design_resp = requests.get(design_url, headers=design_headers)
    
    # デフォルトのメッセージ（取得失敗時用）
    design_title = "タイトル不明"
    view_url = "URL不明"
    thumbnail_url = ""

    if design_resp.status_code == 200:
        design_data = design_resp.json()
        # デザイン情報の取得 (APIのレスポンス構造に合わせて取得)
        design = design_data.get("design", {})
        design_title = design.get("title", "無題のデザイン")
        
        # URLの取得 (view用URLがあればそれを使う)
        urls = design.get("urls", {})
        view_url = urls.get("view_url", urls.get("edit_url", ""))
        
        # サムネイル画像の取得
        thumbnail = design.get("thumbnail", {})
        thumbnail_url = thumbnail.get("url", "")
    else:
        print(f"【警告】デザイン情報の取得に失敗しました: {design_resp.status_code} {design_resp.text}")

    # --- 4. LINEへ送るメッセージを作成 ---
    # テキストメッセージ
    message_text = f"【定期通知】\n本日のデザイン: {design_title}\n\n確認はこちら:\n{view_url}"

    messages_payload = [
        {
            "type": "text",
            "text": message_text
        }
    ]

    # サムネイル画像があれば、画像もLINEに送る設定を追加
    if thumbnail_url:
        messages_payload.append({
            "type": "image",
            "originalContentUrl": thumbnail_url,
            "previewImageUrl": thumbnail_url
        })

    # --- 5. LINEへブロードキャスト送信 ---
    print("LINEへ一斉送信を開始します...")
    line_url = "https://api.line.me/v2/bot/message/broadcast"
    line_headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"
    }
    line_payload = {
        "messages": messages_payload
    }

    line_resp = requests.post(line_url, headers=line_headers, json=line_payload)

    if line_resp.status_code == 200:
        print("LINE送信成功！(Broadcast)")
    else:
        print(f"LINE送信失敗: {line_resp.status_code} {line_resp.text}")

if __name__ == "__main__":
    main()
