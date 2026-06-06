import os, requests
from flask import Flask, render_template, request, jsonify, Response, stream_with_context

app = Flask(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
SHARE_CODE = os.getenv("SHARE_CODE", "").strip()
POLLINATIONS_KEY = os.getenv("POLLINATIONS_KEY", "").strip()

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/optimize-prompt", methods=["POST"])
def optimize_prompt():
    data = request.get_json(force=True)
    if not GROQ_API_KEY:
        return jsonify({"error": "伺服器未設定 GROQ_API_KEY"}), 500
    if SHARE_CODE and data.get("code") != SHARE_CODE:
        return jsonify({"error": "共享密碼錯誤"}), 403

    prompt = data.get("prompt", "").strip()
    if not prompt:
        return jsonify({"error": "請輸入內容"}), 400

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {
                "role": "system",
                "content": "You are an expert AI image prompt engineer. Translate the user input into English and expand it into a highly descriptive, vivid, detailed prompt for image generation. Output ONLY the raw final expanded prompt text. No explanations, markdown, or chat text."
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.7,
    }
    try:
        resp = requests.post(GROQ_URL, json=payload, headers=headers, timeout=20)
        if resp.status_code != 200:
            print(f"Groq Error: {resp.text}")
            return jsonify({"error": f"Groq 連線失敗 ({resp.status_code})"}), 502
        result = resp.json()
        text = result["choices"][0]["message"]["content"].strip()
        if text.startswith('"') and text.endswith('"'):
            text = text[1:-1].strip()
        return jsonify({"optimized_prompt": text})
    except Exception as e:
        return jsonify({"error": f"連線異常: {str(e)[:200]}"}), 502


@app.route("/generate-image")
def generate_image():
    eng_prompt = request.args.get("prompt", "")
    seed = request.args.get("seed", "42")
    if not eng_prompt:
        return "Missing prompt", 400

    # Try multiple URL patterns with retry
    urls = []
    base = f"https://image.pollinations.ai/prompt/{requests.utils.quote(eng_prompt)}"
    # Pattern 1: with nofeed + random seed
    urls.append(f"{base}?width=1024&height=1024&seed={seed}&nofeed=true")
    # Pattern 2: without nofeed
    urls.append(f"{base}?width=1024&height=1024&seed={seed}")
    # Pattern 3: without seed
    urls.append(f"{base}?width=1024&height=1024&nofeed=true")
    # Pattern 4: basic
    urls.append(f"{base}?width=1024&height=1024")

    if POLLINATIONS_KEY:
        urls = [u + f"&key={POLLINATIONS_KEY}" for u in urls]

    import time
    import io
    for url in urls:
        try:
            resp = requests.get(url, timeout=30)
            if resp.status_code == 200:
                return Response(resp.content, mimetype="image/jpeg")
            if resp.status_code == 402:
                time.sleep(1)
                continue
        except Exception:
            continue

    # Fallback: generate placeholder with prompt text
    try:
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new("RGBA", (800, 600), (26, 26, 46, 255))
        d = ImageDraw.Draw(img)
        font = ImageFont.load_default()
        lines = []
        line = ""
        for word in eng_prompt:
            test = f"{line}{word}"
            if d.textlength(test, font=font) > 700:
                lines.append(line)
                line = word
            else:
                line = test
        lines.append(line)
        y = (600 - len(lines) * 30) // 2
        for line in lines:
            tw = d.textlength(line, font=font)
            d.text(((800 - tw) // 2, y), line, fill=(200, 200, 255, 255), font=font)
            y += 30
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return Response(buf.getvalue(), mimetype="image/png")
    except Exception:
        return jsonify({"error": "Pollinations 忙碌，請稍後再試"}), 502


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
