import os
import io
import base64
import time
import urllib.parse

import requests as http_requests

from flask import Flask, request, jsonify, render_template, send_file, Response
from PIL import Image, ImageDraw, ImageFont, ImageSequence

app = Flask(__name__)


def _get_font(size):
    paths = [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "C:\\Windows\\Fonts\\arial.ttf",
        "C:\\Windows\\Fonts\\Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for p in paths:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)

    base_dir = os.path.dirname(os.path.abspath(__file__))
    local_font = os.path.join(base_dir, "NotoSansCJK-Regular.ttc")
    if os.path.exists(local_font):
        return ImageFont.truetype(local_font, size)

    # Download font if on cloud (no local fonts available)
    try:
        FONT_URL = "https://github.com/notofonts/noto-cjk/raw/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf"
        font_path = os.path.join(base_dir, "NotoSansCJKsc-Regular.otf")
        if not os.path.exists(font_path):
            r = http_requests.get(FONT_URL, timeout=30)
            with open(font_path, "wb") as f:
                f.write(r.content)
        return ImageFont.truetype(font_path, size)
    except Exception:
        pass

    return ImageFont.load_default()


def _pil_to_bytes(img, fmt="PNG"):
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    buf.seek(0)
    return buf


def _hex_to_rgb(hx):
    hx = hx.lstrip("#")
    if len(hx) == 3:
        hx = "".join(c * 2 for c in hx)
    return tuple(int(hx[i : i + 2], 16) for i in (0, 2, 4)) + (255,)


# ─── Meme Generator ───────────────────────────────────────────

@app.route("/api/meme", methods=["POST"])
def api_meme():
    top = request.form.get("top", " ")
    bottom = request.form.get("bottom", " ")
    file = request.files.get("image")
    if not file:
        return jsonify({"error": "請上傳圖片"}), 400

    img = Image.open(file.stream).convert("RGBA")
    w, h = img.size

    max_dim = 800
    if w > max_dim or h > max_dim:
        ratio = min(max_dim / w, max_dim / h)
        w, h = int(w * ratio), int(h * ratio)
        img = img.resize((w, h), Image.LANCZOS)

    draw = ImageDraw.Draw(img)
    font_size = max(30, h // 8)
    font = _get_font(font_size)

    for text, pos in [(top, "top"), (bottom, "bottom")]:
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        x = (w - tw) // 2
        y = 10 if pos == "top" else h - th - 10
        for dx in range(-3, 4):
            for dy in range(-3, 4):
                if dx != 0 or dy != 0:
                    draw.text((x + dx, y + dy), text, font=font, fill="black")
        draw.text((x, y), text, font=font, fill="white")

    buf = _pil_to_bytes(img)
    return send_file(buf, mimetype="image/png")


# ─── Text Image ───────────────────────────────────────────────

@app.route("/api/text-image", methods=["POST"])
def api_text_image():
    data = request.get_json(force=True)
    text = data.get("text", "Hello")
    w = int(data.get("width", 800))
    h = int(data.get("height", 600))
    font_size = int(data.get("fontSize", 48))
    align = data.get("align", "置中")
    bg_hex = data.get("bgColor", "#1e1e1e")
    fg_hex = data.get("fgColor", "#ffffff")

    bg_rgb = _hex_to_rgb(bg_hex)
    fg_rgb = _hex_to_rgb(fg_hex)

    img = Image.new("RGBA", (w, h), bg_rgb)
    draw = ImageDraw.Draw(img)
    font = _get_font(font_size)

    lines = text.split("\n")
    line_height = font_size + 10
    total_height = len(lines) * line_height
    start_y = (h - total_height) // 2

    for i, line in enumerate(lines):
        if not line.strip():
            continue
        bbox = draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        if align == "置中":
            x = (w - tw) // 2
        elif align == "靠左":
            x = 20
        else:
            x = w - tw - 20
        y = start_y + i * line_height
        draw.text((x, y), line, font=font, fill=fg_rgb)

    buf = _pil_to_bytes(img)
    return send_file(buf, mimetype="image/png")


# ─── Animation Generator ──────────────────────────────────────

@app.route("/api/animation", methods=["POST"])
def api_animation():
    data = request.get_json(force=True)
    text = data.get("text", "動畫!")
    anim_type = data.get("type", "文字跑馬燈")
    n = int(data.get("frames", 20))
    fps = int(data.get("fps", 10))
    w = int(data.get("width", 400))
    h = int(data.get("height", 200))
    bg_hex = data.get("bgColor", "#000000")
    fg_hex = data.get("fgColor", "#ffffff")

    bg = _hex_to_rgb(bg_hex)
    fg = _hex_to_rgb(fg_hex)

    font = _get_font(40)

    frames = []
    if anim_type == "文字跑馬燈":
        frames = _marquee(text, w, h, font, bg, fg, n)
    elif anim_type == "文字淡入淡出":
        frames = _fade(text, w, h, font, bg, fg, n)
    elif anim_type == "文字彈跳":
        frames = _bounce(text, w, h, font, bg, fg, n)
    elif anim_type == "顏色漸變":
        frames = _color_shift(text, w, h, font, bg, fg, n)
    elif anim_type == "旋轉文字":
        frames = _rotate_text(text, w, h, font, bg, fg, n)

    if not frames:
        return jsonify({"error": "生成失敗"}), 500

    buf = io.BytesIO()
    frames_rgb = [f.convert("RGBA") for f in frames]
    frames_rgb[0].save(
        buf,
        save_all=True,
        append_images=frames_rgb[1:],
        duration=1000 // fps,
        loop=0,
        disposal=2,
        format="GIF",
    )
    buf.seek(0)
    return send_file(buf, mimetype="image/gif")


def _marquee(text, w, h, font, bg, fg, n):
    frames = []
    bbox = font.getbbox(text)
    tw = bbox[2] - bbox[0]
    for i in range(n):
        img = Image.new("RGBA", (w, h), bg)
        draw = ImageDraw.Draw(img)
        x = w - int((w + tw) * i / n)
        y = (h - bbox[3] + bbox[1]) // 2
        draw.text((x, y), text, font=font, fill=fg)
        frames.append(img)
    return frames


def _fade(text, w, h, font, bg, fg, n):
    frames = []
    bbox = font.getbbox(text)
    x = (w - (bbox[2] - bbox[0])) // 2
    y = (h - bbox[3] + bbox[1]) // 2
    half = n // 2
    for i in range(n):
        img = Image.new("RGBA", (w, h), bg)
        draw = ImageDraw.Draw(img)
        if i < half:
            alpha = int(255 * i / half) if half > 0 else 255
        else:
            alpha = int(255 * (n - 1 - i) / (n - half - 1)) if n - half - 1 > 0 else 0
        draw.text((x, y), text, font=font, fill=(fg[0], fg[1], fg[2], alpha))
        frames.append(img)
    return frames


def _bounce(text, w, h, font, bg, fg, n):
    frames = []
    bbox = font.getbbox(text)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = (w - tw) // 2
    for i in range(n):
        img = Image.new("RGBA", (w, h), bg)
        draw = ImageDraw.Draw(img)
        progress = i / (n - 1) if n > 1 else 0
        y = int(abs(h - th) * (1 - abs(2 * progress - 1)))
        draw.text((x, y), text, font=font, fill=fg)
        frames.append(img)
    return frames


def _color_shift(text, w, h, font, bg, fg, n):
    frames = []
    bbox = font.getbbox(text)
    x = (w - (bbox[2] - bbox[0])) // 2
    y = (h - bbox[3] + bbox[1]) // 2
    for i in range(n):
        img = Image.new("RGBA", (w, h), bg)
        draw = ImageDraw.Draw(img)
        r = min(255, int(255 * i / n))
        g = min(255, int(255 * (n - i) / n))
        b = min(255, int(128 * abs(n / 2 - i) / (n / 2)))
        draw.text((x, y), text, font=font, fill=(r, g, b, 255))
        frames.append(img)
    return frames


def _rotate_text(text, w, h, font, bg, fg, n):
    frames = []
    bbox = font.getbbox(text)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    for i in range(n):
        txt_img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(txt_img)
        draw.text(((w - tw) // 2, (h - th) // 2), text, font=font, fill=fg)
        angle = 360 * i / n
        rotated = txt_img.rotate(angle, expand=False, center=(w // 2, h // 2))
        img = Image.new("RGBA", (w, h), bg)
        img = Image.alpha_composite(img, rotated)
        frames.append(img)
    return frames


# ─── AI Image Generation ───────────────────────────────────

@app.route("/api/ai-image", methods=["POST"])
def api_ai_image():
    data = request.get_json(force=True)
    prompt = data.get("prompt", "")
    if not prompt:
        return jsonify({"error": "請輸入描述"}), 400

    provider = data.get("provider", "pollinations")
    api_key = data.get("apiKey", "")
    w = int(data.get("width", 1024))
    h = int(data.get("height", 1024))

    try:
        if provider == "openai":
            return _gen_openai_image(prompt, w, h, api_key)
        elif provider == "replicate":
            return _gen_replicate_image(prompt, w, h, api_key)
        else:
            return _gen_pollinations_image(prompt, w, h)
    except Exception as e:
        return jsonify({"error": f"生成失敗: {str(e)}"}), 502


def _gen_pollinations_image(prompt, w, h):
    url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}"
    resp = http_requests.get(url, timeout=60)
    if resp.status_code != 200:
        return jsonify({
            "error": f"Pollinations 生成失敗 ({resp.status_code})，請稍後重試或更換其他提供者"
        }), 502
    return send_file(
        io.BytesIO(resp.content),
        mimetype=resp.headers.get("Content-Type", "image/png"),
    )


def _gen_openai_image(prompt, w, h, api_key):
    if not api_key:
        return jsonify({"error": "請輸入 OpenAI API Key"}), 400
    resp = http_requests.post(
        "https://api.openai.com/v1/images/generations",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": "dall-e-3",
            "prompt": prompt,
            "n": 1,
            "size": f"{w}x{h}" if w == h else "1024x1024",
        },
        timeout=30,
    )
    if resp.status_code != 200:
        return jsonify({"error": f"OpenAI 錯誤: {resp.json().get('error', {}).get('message', resp.status_code)}"}), 502
    img_url = resp.json()["data"][0]["url"]
    img_resp = http_requests.get(img_url, timeout=30)
    return send_file(io.BytesIO(img_resp.content), mimetype="image/png")


def _gen_replicate_image(prompt, w, h, api_key):
    if not api_key:
        return jsonify({"error": "請輸入 Replicate API Key"}), 400
    resp = http_requests.post(
        "https://api.replicate.com/v1/models/black-forest-labs/flux-dev/predictions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={"input": {"prompt": prompt, "width": w, "height": h}},
        timeout=10,
    )
    if resp.status_code != 201:
        return jsonify({"error": f"Replicate 錯誤: {resp.text[:200]}"}), 502

    prediction = resp.json()
    get_url = prediction["urls"]["get"]

    # Poll until complete
    for _ in range(60):
        http_requests.get("https://api.replicate.com/v1/predictions/" + prediction["id"],
                          headers={"Authorization": f"Bearer {api_key}"})
        time.sleep(1)
        status_resp = http_requests.get(get_url, headers={"Authorization": f"Bearer {api_key}"})
        status = status_resp.json()
        if status["status"] == "succeeded":
            img_url = status["output"][0]
            img_resp = http_requests.get(img_url, timeout=30)
            return send_file(io.BytesIO(img_resp.content), mimetype="image/png")
        elif status["status"] == "failed":
            return jsonify({"error": "Replicate 生成失敗"}), 502
    return jsonify({"error": "Replicate 生成超時"}), 504


# ─── AI Video / Animation ─────────────────────────────────

@app.route("/api/ai-video", methods=["POST"])
def api_ai_video():
    data = request.get_json(force=True)
    prompt = data.get("prompt", "")
    if not prompt:
        return jsonify({"error": "請輸入描述"}), 400

    provider = data.get("provider", "pollinations")
    api_key = data.get("apiKey", "")

    try:
        if provider == "replicate":
            return _gen_replicate_video(prompt, api_key)
        else:
            url = f"https://gen.pollinations.ai/video/{urllib.parse.quote(prompt)}"
            resp = http_requests.get(url, timeout=120, stream=True)
            if resp.status_code != 200:
                return jsonify({
                    "error": f"Pollinations 影片生成失敗 ({resp.status_code})，請稍後重試"
                }), 502
            return Response(
                resp.iter_content(chunk_size=8192),
                content_type=resp.headers.get("Content-Type", "video/mp4"),
            )
    except Exception as e:
        return jsonify({"error": f"連線失敗: {str(e)}"}), 502


def _gen_replicate_video(prompt, api_key):
    if not api_key:
        return jsonify({"error": "請輸入 Replicate API Key"}), 400
    resp = http_requests.post(
        "https://api.replicate.com/v1/models/wan-video/wan-2.1/predictions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={"input": {"prompt": prompt}},
        timeout=10,
    )
    if resp.status_code != 201:
        return jsonify({"error": f"Replicate 影片錯誤: {resp.text[:200]}"}), 502

    prediction = resp.json()
    get_url = prediction["urls"]["get"]

    for _ in range(120):
        time.sleep(2)
        status_resp = http_requests.get(get_url, headers={"Authorization": f"Bearer {api_key}"})
        status = status_resp.json()
        if status["status"] == "succeeded":
            video_url = status["output"][0]
            video_resp = http_requests.get(video_url, timeout=60)
            return send_file(io.BytesIO(video_resp.content), mimetype="video/mp4")
        elif status["status"] == "failed":
            return jsonify({"error": "Replicate 影片生成失敗"}), 502
    return jsonify({"error": "Replicate 影片生成超時"}), 504


# ─── Main Page ────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    print("=" * 50)
    print("  圖片動畫生成器 Web 版")
    print(f"  本機開啟: http://127.0.0.1:{port}")
    print(f"  區域網路: http://<你的IP>:{port}")
    print(f"  雲端部署: 使用 PORT={port} gunicorn web_app:app")
    print("=" * 50)
    app.run(host="0.0.0.0", port=port, debug=debug)
