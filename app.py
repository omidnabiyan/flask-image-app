import os
from flask import Flask, render_template, request, send_file, jsonify
import cv2
import numpy as np
from io import BytesIO
from PIL import Image

app = Flask(__name__, static_folder="static", template_folder="templates")

# global images (simple in-memory storage)
cv_img = None          # BGR original (numpy)
processed_img = None   # last processed grayscale (uint8)
history = []           # stack of processed images for undo (list of uint8)

def process_image_from_params(base_bgr, params):
    """بازتولید pipeline پردازش از نسخه‌ی دسکتاپی با پارامترهای دریافتی"""
    if base_bgr is None:
        return None
    gray = cv2.cvtColor(base_bgr, cv2.COLOR_BGR2GRAY)
    img = gray.copy().astype(np.float32)

    # CLAHE (Local Contrast)
    local_contrast = float(params.get("Local Contrast", 3.0))
    clahe = cv2.createCLAHE(clipLimit=max(1.0, local_contrast / 2.0), tileGridSize=(8, 8))
    img = clahe.apply(img.astype(np.uint8)).astype(np.float32)

    # Shadows / Highlights
    shadows_val = float(params.get("Shadows", 0.0)) / 100.0
    highlights_val = float(params.get("Highlights", 0.0)) / 100.0
    img_f = img / 255.0
    if abs(shadows_val) > 1e-6:
        mask = img_f < 0.5
        img_f = np.where(mask, np.clip(img_f + shadows_val * (0.5 - img_f), 0, 1), img_f)
    if abs(highlights_val) > 1e-6:
        mask = img_f >= 0.5
        img_f = np.where(mask, np.clip(img_f + highlights_val * (img_f - 0.5), 0, 1), img_f)
    img = (img_f * 255.0).astype(np.uint8).astype(np.float32)

    # Contrast & Brightness
    alpha = float(params.get("کنتراست", 100)) / 100.0
    beta = float(params.get("روشنایی", 0))
    img = cv2.convertScaleAbs(img, alpha=alpha, beta=beta).astype(np.float32)

    # Gamma
    gamma = float(params.get("گاما", 100)) / 100.0
    if abs(gamma - 1.0) > 1e-6:
        inv_gamma = 1.0 / gamma
        table = (np.linspace(0, 1, 256, dtype=np.float32) ** inv_gamma) * 255.0
        lut = table.astype(np.uint8)
        img = cv2.LUT(img.astype(np.uint8), lut).astype(np.float32)

    # Tone curve (Gamma / Tone Curve)
    tone = float(params.get("Gamma / Tone Curve", 10.0)) / 10.0
    if abs(tone - 1.0) > 1e-6:
        inv_tone = 1.0 / tone
        table_tone = (np.linspace(0, 1, 256, dtype=np.float32) ** inv_tone) * 255.0
        lut_tone = table_tone.astype(np.uint8)
        img = cv2.LUT(img.astype(np.uint8), lut_tone).astype(np.float32)

    # Black / White levels
    black = float(params.get("سطح سیاه", 0.0))
    white = float(params.get("سطح سفید", 255.0))
    if white <= black:
        white = black + 1.0
    img = np.clip((img - black) * (255.0 / (white - black)), 0, 255).astype(np.uint8)

    # Blur
    raw_blur_value = float(params.get("Blur", 1.0))
    blur_val = int(round(2.0 * (raw_blur_value / 10.0) + 1))
    if blur_val < 1:
        blur_val = 1
    if blur_val % 2 == 0:
        blur_val += 1
    if blur_val > 1:
        img = cv2.GaussianBlur(img, (blur_val, blur_val), 0)

    # Sharpness (unsharp-like)
    slider = float(params.get("تیزی", 0.0))
    if slider > 0:
        normalized = slider / 100.0
        amount = (normalized ** 2) * 0.8
        k = 1 + 2 * int(round(normalized * 4))
        if k % 2 == 0:
            k += 1
        if k <= 1:
            blurred = img.copy()
        else:
            blurred = cv2.GaussianBlur(img, (k, k), 0)
        img = cv2.addWeighted(img.astype(np.float32), 1.0 + amount, blurred.astype(np.float32), -amount, 0)
        img = np.clip(img, 0, 255).astype(np.uint8)

    # Sharpness2 (kernel)
    sharp2_val = float(params.get("تیزی۲", 0.0)) / 100.0
    if sharp2_val > 0:
        kernel = np.array([[0, -1, 0], [-1, 5 + sharp2_val, -1], [0, -1, 0]], dtype=np.float32)
        img = cv2.filter2D(img, -1, kernel)

    return img.astype(np.uint8)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload():
    global cv_img, processed_img, history
    f = request.files.get("image")
    if not f:
        return jsonify({"error": "No file"}), 400
    data = f.read()
    arr = np.frombuffer(data, np.uint8)
    bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if bgr is None:
        return jsonify({"error": "Invalid image"}), 400
    cv_img = bgr
    # initialize processed_img (grayscale)
    processed_img = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    history = []
    # return a quick preview (encoded jpeg)
    _, buf = cv2.imencode(".jpg", processed_img)
    return send_file(BytesIO(buf.tobytes()), mimetype="image/jpeg")

@app.route("/update_preview", methods=["POST"])
def update_preview():
    global cv_img, processed_img
    if cv_img is None:
        return jsonify({"error": "No image uploaded"}), 400
    params = request.get_json() or {}
    img = process_image_from_params(cv_img, params)
    if img is None:
        return jsonify({"error": "processing failed"}), 500
    processed_img = img
    _, buf = cv2.imencode(".jpg", processed_img)
    return send_file(BytesIO(buf.tobytes()), mimetype="image/jpeg")

@app.route("/apply", methods=["POST"])
def apply_and_save_history():
    """وقتی کاربر Enhance را می‌زند — پردازش را انجام بده و در history ذخیره کن"""
    global cv_img, processed_img, history
    if cv_img is None:
        return jsonify({"error": "No image uploaded"}), 400
    params = request.get_json() or {}
    img = process_image_from_params(cv_img, params)
    if img is None:
        return jsonify({"error": "processing failed"}), 500
    # push to history
    history.append(img.copy())
    if len(history) > 20:
        history.pop(0)
    processed_img = img
    _, buf = cv2.imencode(".jpg", processed_img)
    return send_file(BytesIO(buf.tobytes()), mimetype="image/jpeg")

@app.route("/undo", methods=["POST"])
def undo():
    global processed_img, history
    if history:
        # pop last state
        history.pop()  # remove last applied
        if history:
            processed_img = history[-1].copy()
        else:
            processed_img = None
    else:
        processed_img = None
    if processed_img is None:
        return jsonify({"empty": True}), 200
    _, buf = cv2.imencode(".jpg", processed_img)
    return send_file(BytesIO(buf.tobytes()), mimetype="image/jpeg")

@app.route("/download", methods=["GET"])
def download():
    global processed_img
    if processed_img is None:
        return jsonify({"error": "No processed image"}), 400
    # return PNG for lossless
    _, buf = cv2.imencode(".png", processed_img)
    return send_file(BytesIO(buf.tobytes()), mimetype="image/png", as_attachment=True, download_name="processed.png")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug, host="0.0.0.0", port=port)
