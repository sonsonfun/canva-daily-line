import os
import requests
import base64
import json
import sys
import time
from google import genai
from PIL import Image
from io import BytesIO

# 設定
REFRESH_TOKEN = os.environ["CANVA_REFRESH_TOKEN"]
CLIENT_ID = os.environ["CANVA_CLIENT_ID"]
CLIENT_SECRET = os.environ["CANVA_CLIENT_SECRET"]
DESIGN_ID = os.environ["CANVA_DESIGN_ID"]
LINE_TOKEN = os.environ["LINE_TOKEN"]
LINE_USER_ID = os.environ["LINE_USER_ID"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

# 最新のAI初期化
client = genai.Client(api_key=GEMINI_API_KEY)

def get_new_tokens():
    url = "https://api.canva.com/rest/v1/oauth/token"
    auth_str = f"{CLIENT_ID}:{CLIENT_SECRET}"
    b64_auth = base64.b64encode(auth_str.encode()).decode()
    headers = {"Authorization": f"Basic {b64_auth}", "Content-Type": "application/x-www-form-urlencoded"}
    data = {"grant_type": "refresh_token", "refresh_token": REFRESH_TOKEN}
    resp = requests.post(url, headers=headers, data=data)
    if resp.status_code != 200:
        return None, None
    return resp.json().get("access_token"), resp.json().get("refresh_token")

def export_images(access_token):
    """1枚目と2枚目をまとめて書き出す"""
    print("Canva: 画像を生成中...")
    url = "https://api.canva.com/rest/v1/exports"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    
    payload = {
        "design_id": DESIGN_ID, 
        "format": {"type": "jpg", "quality": 100}, 
        "pages": [1, 2] # ← 1枚目と2枚目を指定
    }
    
    resp = requests.post(url, headers=headers, json=payload)
    if resp.status_code != 200:
        print(f"Export Error: {resp.text}")
        return None
        
    job_id = resp.json().get("job", {}).get("id")
    
    for _ in range(20): # 最大60秒待機
        time.sleep(3)
        check_resp = requests.get(f"{url}/{job_id}", headers=headers)
        job = check_resp.json().get("job", {})
        if job.get("status") == "success":
            # 成功したら画像のURLリストを返す
            return job.get("urls", [])
    return None

def analyze_image(image_bytes, page_num):
    """画像をAIで解析する"""
    print(f"Gemini: {page_num}枚目を解析中...")
    try:
        image = Image.open(BytesIO(image_bytes))
        prompt = f"""
        これは{page_num}枚目の画像（エクセル表や資料）です。
        内容を読み取り、重要なポイントを箇条書きでまとめてください。
        もし文字がない画像なら「画像のみ」と判断してください。
        """
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=[prompt, image]
        )
        result = response.text.strip()
        if "解析不可" in result or not result:
            return None
        return result
    except Exception as e:
        print(f"Gemini Error: {e}")
        return None

def main():
    # 1. トークン更新
    access_token, new_refresh_token = get_new_tokens()
    if not access_token: sys.exit(1)

    # 新しいトークンをGitHubに保存
    if new_refresh_token:
        with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
            f.write(f"new_refresh_token={new_refresh_token}\n")

    # 2. 画像URLを取得（2枚分）
    image_urls = export_images(access_token)
    if not image_urls:
        print("画像の取得に失敗しました")
        sys.exit(1)

    line_url = "https://api.line.me/v2/bot/message/push"
    headers = {"Authorization": f"Bearer {LINE_TOKEN}", "Content-Type": "application/json"}
    
    # キャッシュ回避用の時間スタンプ
    timestamp = int(time.time())

    # 3. 1枚ずつ処理してLINE送信
    for i, url in enumerate(image_urls):
        page_num = i + 1 # 1ページ目、2ページ目...
        
        # 画像ダウンロード
        img_resp = requests.get(url)
        
        # AI解析
        text_msg = analyze_image(img_resp.content, page_num)
        
        # LINEメッセージ作成
        cache_free_url = f"{url}&t={timestamp}_{page_num}"
        messages = [{"type": "image", "originalContentUrl": cache_free_url, "previewImageUrl": cache_free_url}]
        
        if text_msg:
            header = f"【{page_num}枚目の解析】\n"
            messages.append({"type": "text", "text": header + text_msg})
        
        # 送信
        payload = {"to": LINE_USER_ID, "messages": messages}
        requests.post(line_url, headers=headers, json=payload)
        print(f"{page_num}枚目を送信しました")
        time.sleep(1) # 送信順序を守るため少し待つ

if __name__ == "__main__":
    main()
