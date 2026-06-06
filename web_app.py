import os, requests, io, random
from flask import Flask, render_template, request, send_file, jsonify
from PIL import Image, ImageDraw, ImageFont

app = Flask(__name__)


def _get_font(size):
    paths = [
        "/System/Library/Fonts/Helvetica.ttc", "/System/Library/Fonts/Supplemental/Arial.ttf",
        "C:\\Windows\\Fonts\\arial.ttf", "C:\\Windows\\Fonts\\Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/TTF/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for p in paths:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/generate", methods=["POST"])
def generate():
    data = request.json
    prompt = data.get("prompt", "")
    if not prompt:
        return jsonify({"error": "請輸入提示詞"}), 400
    w, h = int(data.get("width", 1024)), int(data.get("height", 1024))
    try:
        url = f"https://image.pollinations.ai/prompt/{requests.utils.quote(prompt)}?width={w}&height={h}&seed={random.randint(0,99999)}"
        resp = requests.get(url, timeout=30)
        if resp.status_code == 200:
            return send_file(io.BytesIO(resp.content), mimetype="image/jpeg")
        return jsonify({"error": f"生成失敗 ({resp.status_code})"}), 502
    except Exception as e:
        return jsonify({"error": str(e)[:200]}), 502


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
