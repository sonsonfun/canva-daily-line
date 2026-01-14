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
CANVA_CLIENT_ID = os.environ["CANVA_CLIENT_ID"]
CANVA_CLIENT_SECRET = os.environ["CANVA_CLIENT_SECRET"]
CANVA_DESIGN_ID = os.environ["CANVA_DESIGN_ID"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
LINE_CHANNEL_ACCESS_TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]

# トークンファイルのパス
TOKEN_FILE = "canva_token.txt"

def get_canva_access_token():
    try:
        with open(TOKEN_FILE, "r") as f:
            refresh_token = f.read().strip()
    except FileNotFoundError:
        raise Exception(f"{TOKEN_FILE} が見つかりません。最新のトークンを貼ったファイルを作成してください。")

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
    # 1枚目だけを対象にする
    print("Geminiで1ページ目の画像を解析中...")
    
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
    
    # プロンプト
    prompt = """
1ページ目の画像を読み取り、以下のルールに従って人物ごとにタスクを文字起こししてください。
画像はスプレッドシート形式です。左側の列が「期日」、右側の列が「タスク内容」に対応しています。

【重要：期日の読み取りルール】
・左側の「期日」セルが空欄（空白）の場合は、絶対に日付を推測せず、必ず「（未定）」と記述してください。
・日付が明記されている場合のみ、「M/D」形式に変換してください。
・「空欄＝（未定）」の判定を最優先してください。

【出力ルール】
1. 人物ごとにセクションを分けてください（見出し記号「###」は使わず、「【氏名】」の形式で区切ってください）。
2. 各タスクは以下の形式で記述してください。
   期日：内容
3. リストの並び順は、日付が早い順（昇順）に並べ替えてください。
   - 「（未定）」のタスクは、リストの最後にまとめて配置してください。
4. タスク内容が空欄の場合は「（なし）」と記載してください。
5. 全ての出力の最後に、画像の内容とは無関係に、以下を必ず出力してください。
https://www.canva.com/design/DAG9nTLkHxs/QXTXrj2mJFEhVT1MwjXd0Q/edit
    """
    
    contents_list.append(prompt)

    response = client.models.generate_content(
        model='gemini-flash-latest',
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
