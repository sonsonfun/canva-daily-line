import os
import time
import base64
import requests
import json
from google import genai
from google.genai import types
from linebot import LineBotApi
from linebot.models import TextSendMessage, ImageSendMessage

# --- 環境変数の取得 ---
# 実行環境にこれらの環境変数が設定されていることを確認してください
CANVA_CLIENT_ID = os.environ["CANVA_CLIENT_ID"]
CANVA_CLIENT_SECRET = os.environ["CANVA_CLIENT_SECRET"]
CANVA_DESIGN_ID = os.environ["CANVA_DESIGN_ID"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
LINE_CHANNEL_ACCESS_TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]

# トークンファイルのパス（初回は手動で作成が必要）
TOKEN_FILE = "canva_token.txt"

def get_canva_access_token():
    try:
        with open(TOKEN_FILE, "r") as f:
            refresh_token = f.read().strip()
    except FileNotFoundError:
        raise Exception(f"{TOKEN_FILE} が見つかりません。最新のリフレッシュトークンを貼ったファイルを作成してください。")

    url = "https://api.canva.com/rest/v1/oauth/token"
    auth_str = f"{CANVA_CLIENT_ID}:{CANVA_CLIENT_SECRET}"
    b64_auth = base64.b64encode(auth_str.encode()).decode()
    
    headers = {
        "Authorization": f"Basic {b64_auth}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token
    }

    print("Canvaアクセストークンを更新中...")
    resp = requests.post(url, headers=headers, data=data)
    
    if resp.status_code != 200:
        raise Exception(f"Canva Token Error: {resp.status_code} {resp.text}")
    
    tokens = resp.json()
    
    if "refresh_token" in tokens:
        new_refresh_token = tokens["refresh_token"]
        with open(TOKEN_FILE, "w") as f:
            f.write(new_refresh_token)
        print("★新しいリフレッシュトークンを canva_token.txt に保存しました。")
    
    return tokens["access_token"]

def export_canva_design(access_token):
    url = "https://api.canva.com/rest/v1/exports"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    # ここで type: png を指定しているので、Geminiには画像が渡ります
    data = {
        "design_id": CANVA_DESIGN_ID,
        "format": {"type": "png"}
    }
    
    print(f"デザイン({CANVA_DESIGN_ID})の高画質エクスポート(PNG)を開始...")
    resp = requests.post(url, headers=headers, json=data)
    
    if resp.status_code != 200:
        raise Exception(f"Canva Export Error: {resp.text}")
    
    job_id = resp.json()["job"]["id"]
    
    for _ in range(30):
        time.sleep(3)
        status_resp = requests.get(f"{url}/{job_id}", headers=headers)
        if status_resp.status_code == 200:
            job_data = status_resp.json()["job"]
            status = job_data["status"]
            
            if status == "success":
                image_urls = job_data["urls"]
                print(f"エクスポート成功: {len(image_urls)}枚の画像を取得しました")
                return image_urls
            elif status == "failed":
                raise Exception(f"Canva Export Failed: {job_data.get('error')}")
    
    raise Exception("Canva Export Timeout")

def analyze_image_with_gemini(image_urls):
    # ★変更点：モデルをPro版にするため、ログを変更
    print("Gemini (1.5 Pro) で1ページ目の画像を解析中...")
    
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    contents_list = []
    
    if not image_urls:
        raise Exception("画像URLが取得できませんでした")

    # リストの最初のURL（1ページ目）のみを取得
    first_url = image_urls[0]
    
    print(f"  - 1ページ目をダウンロード中...")
    img_resp = requests.get(first_url)
    if img_resp.status_code == 200:
        contents_list.append(
            types.Part.from_bytes(data=img_resp.content, mime_type='image/png')
        )
    else:
        raise Exception("画像のダウンロードに失敗しました")
    
    # ★変更点：ハルシネーション（嘘の日付）を防ぐための厳格なプロンプト
    prompt = """
あなたは優秀なデータ入力担当者です。
1ページ目の画像を読み取り、以下の手順で正確に文字起こしを行ってください。
画像はスプレッドシート形式です。

【手順1：事実確認（重要）】
まず表の「左の列（期日）」を上から順に見て、以下のチェックを行ってください。
・文字（インク）が書かれているか？
・ただの空白ではないか？
・行番号（1, 2, 3...）やノイズではないか？

【手順2：期日の厳格な判定】
・セルに「/」または「月」という文字が明確にある場合のみ、日付として採用してください。
・それ以外（空白、行番号のみ、数字のみ）は、絶対に日付を捏造せず「（未定）」として処理してください。推測は禁止です。

【手順3：出力】
判定に基づき、人物ごとに以下のフォーマットで出力してください。

■出力フォーマット
【氏名】
M/D：タスク内容
（未定）：タスク内容

■並び順とルール
・日付順（昇順）に並べる。
・（未定）はリストの最後にまとめる。
・タスク内容が空欄の場合は「（なし）」とする。
・見出し記号「###」は使わない。

■最後に必ず出力する定型文
https://www.canva.com/design/DAG9nTLkHxs/QXTXrj2mJFEhVT1MwjXd0Q/edit
    """
    
    contents_list.append(prompt)

    # ★変更点：ここを 'gemini-1.5-pro' に変更して精度を最大化
    response = client.models.generate_content(
        model='gemini-1.5-pro',
        contents=contents_list
    )
    
    if not response.text:
        raise Exception("Gemini returned empty response")
        
    return response.text

def send_line_message(text, image_urls):
    print("LINE友だち全員へ一斉送信中...")
    line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
    
    messages = []
    
    # --- 1. 画像メッセージを先に追加 ---
    # (最大4枚まで、LINEの一斉送信上限5通ルールに収めるため)
    max_images = 4
    for i, url in enumerate(image_urls[:max_images]):
        messages.append(
            ImageSendMessage(original_content_url=url, preview_image_url=url)
        )
    
    # --- 2. テキストメッセージを後に追加 ---
    messages.append(TextSendMessage(text=text))
    
    # broadcastを使用
    line_bot_api.broadcast(messages)
    
    print("送信完了")

def main():
    try:
        print("--- 処理開始 ---")
        access_token = get_canva_access_token()
        image_urls = export_canva_design(access_token)
        gemini_text = analyze_image_with_gemini(image_urls)
        print(f"生成されたメッセージ:\n{gemini_text}")
        send_line_message(gemini_text, image_urls)
        print("--- 全工程完了 ---")
    except Exception as e:
        print(f"エラー発生: {e}")
        exit(1)

if __name__ == "__main__":
    main()
