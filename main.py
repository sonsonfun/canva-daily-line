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

    # 環境変数が足りない場合のチェック
    if not all([CANVA_CLIENT_ID, CANVA_CLIENT_SECRET, CANVA_REFRESH_TOKEN, LINE_CHANNEL_ACCESS_TOKEN]):
        print("Error: 必要な環境変数が設定されていません。")
        return

    # --- 2. Canva アクセストークンの更新 (Refresh Token Flow) ---
    print("Canvaトークンを更新中...")
    
    # Basic認証ヘッダーの作成
    auth_str = f"{CANVA_CLIENT_ID}:{CANVA_CLIENT_SECRET}"
    b64_auth_str = base64.b64encode(auth_str.encode()).decode()

    token_url = "https://api.canva.com/rest/v1/oauth/token"
    headers = {
        "Authorization": f"Basic {b64_auth_str}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "grant_type": "refresh_token",
        "refresh_token": CANVA_REFRESH_TOKEN
    }

    response = requests.post(token_url, headers=headers, data=data)
    
    if response.status_code != 200:
        print(f"【エラー】トークン更新失敗: {response.status_code} {response.text}")
        exit(1)

    tokens = response.json()
    access_token = tokens.get("access_token")
    new_refresh_token = tokens.get("refresh_token")

    # --- 3. 新しいリフレッシュトークンをGitHub Actionsに渡す ---
    # YAML側の steps.script_step.outputs.new_refresh_token で受け取れるようにする
    if new_refresh_token:
        print(f"新しいリフレッシュトークンを取得しました。")
        # GITHUB_OUTPUT 環境変数が存在する場合（GitHub Actions上で実行している場合）
        if "GITHUB_OUTPUT" in os.environ:
            with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                f.write(f"new_refresh_token={new_refresh_token}\n")
    
    # --- 4. Canvaから情報を取得する (必要であれば実装) ---
    # ※ここでは例として、デザインIDを含んだメッセージを作成します。
    # もしCanva APIでデザインの詳細を取得したい場合は、
    # ここで access_token を使って requests.get(...) してください。
    
    message_text = f"【お知らせ】\nCanvaデザイン(ID: {CANVA_DESIGN_ID}) の定期通知です。\n\n今日も一日がんばりましょう！"

    # --- 5. LINEへブロードキャスト送信 (全員に送信) ---
    print("LINEへ一斉送信を開始します...")

    line_url = "https://api.line.me/v2/bot/message/broadcast"
    line_headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"
    }
    line_payload = {
        "messages": [
            {
                "type": "text",
                "text": message_text
            }
        ]
    }

    line_response = requests.post(line_url, headers=line_headers, json=line_payload)

    if line_response.status_code == 200:
        print("LINE送信成功！(Broadcast)")
    else:
        print(f"LINE送信失敗: {line_response.status_code} {line_response.text}")

if __name__ == "__main__":
    main()
