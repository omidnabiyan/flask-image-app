import io
import os
from flask import Flask, render_template, request, send_file, jsonify
import numpy as np
import cv2
from PIL import Image

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max upload

def read_image_from_file_storage(file_storage):
    # خواندن بایت‌ها به numpy و decode با OpenCV
    data = file_storage.read()
    arr = np.frombuffer(data, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return img

def process_image_cv(img_bgr, params):
    """پارامترها را به عنوان دیکشنری می‌گیرد و یک تصویر grayscale (uint8) برمی‌گرداند."""
    if img_bgr is None:
        return None
    # تبدیل به grayscale
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    img = gray.astype(np.uint8).copy()

    # CLAHE (Local Contrast)
    local_contrast = max(1.0, float(params.get('local_contrast', 3)) / 2.0)
    clahe = cv2.createCLAHE(clipLimit=local_contrast, tileGridSize=(8, 8))
    img = clahe.apply(img)

    # Shadows & Highlights
    img_f = img.astype(np.float32) / 255.0
    shadows_val = float(params.get('shadows', 0)) / 100.0
    highlights_val = float(params.get('highlights', 0)) / 100.0
    if abs(shadows_val) > 1e-6:
        mask = img_f < 0.5
        img_f = np.where(mask, np.clip(img_f + shadows_val * (0.5 - img_f), 0, 1), img_f)
    if abs(highlights_val) > 1e-6:
        mask = img_f >= 0.5
        img_f = np.where(mask, np.clip(img_f + highlights_val * (img_f - 0.5), 0, 1), img_f)
    img = (img_f * 255).astype(np.uint8)

    # Contrast & Brightness
    alpha = float(params.get('contrast', 100)) / 100.0
    beta = float(params.get('brightness', 0))
    img = cv2.convertScaleAbs(img, alpha=alpha, beta=beta)

    # Gamma
    gamma = float(params.get('gamma', 100)) / 100.0
    if abs(gamma - 1.0) > 1e-6:
        inv_gamma = 1.0 / gamma
        table = (np.linspace(0, 1, 256, dtype=np.float32) ** inv_gamma) * 255.0
        lut = table.astype(np.uint8)
        img = cv2.LUT(img, lut)

    # Tone curve (Gamma / Tone Curve)
    tone = float(params.get('tone', 10)) / 10.0
    if abs(tone - 1.0) > 1e-6:
        inv_tone = 1.0 / tone
        table_tone = (np.linspace(0, 1, 256, dtype=np.float32) ** inv_tone) * 255.0
        lut_tone = table_tone.astype(np.uint8)
        img = cv2.LUT(img, lut_tone)

    # Black / White Levels
    black = int(params.get('black_level', 0))
    white = int(params.get('white_level', 255))
    if white <= black:
        white = black + 1
    img = np.clip((img.astype(np.float32) - black) * (255.0 / (white - black)), 0, 255).astype(np.uint8)

    # Blur
    raw_blur_value = int(params.get('blur', 1))
    blur_val = int(round(2.0 * (raw_blur_value / 10.0) + 1))
    if blur_val < 1:
        blur_val = 1
    if blur_val % 2 == 0:
        blur_val += 1
    if blur_val > 1:
        img = cv2.GaussianBlur(img, (blur_val, blur_val), 0)

    # Sharpness (soft)
    slider = int(params.get('sharp', 0))
    if slider > 0:
        normalized = slider / 100.0
        amount = (normalized ** 2) * 0.8
        k = 1 + 2 * int(round(normalized * 4))
        if k < 1:
            k = 1
        if k == 1:
            blurred = img.copy()
        else:
            if k % 2 == 0:
                k += 1
            blurred = cv2.GaussianBlur(img, (k, k), 0)
        img = cv2.addWeighted(img, 1.0 + amount, blurred, -amount, 0)

    # Sharp2 (kernel)
    sharp2_val = float(params.get('sharp2', 0)) / 100.0
    if sharp2_val > 0:
        kernel = np.array(
            [[0, -1, 0],
             [-1, 5 + sharp2_val, -1],
             [0, -1, 0]],
            dtype=np.float32
        )
        img = cv2.filter2D(img, -1, kernel)

    return img

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/process", methods=["POST"])
def process():
    # پارامترها را از فرم بگیر
    file = request.files.get("image")
    if not file:
        return jsonify({"error": "No file uploaded"}), 400

    # خواندن تصویر
    img_bgr = read_image_from_file_storage(file)
    if img_bgr is None:
        return jsonify({"error": "Cannot decode image"}), 400

    # خواندن پارامترها (با نام‌هایی که در front-end ارسال می‌کنیم)
    params = {
        "brightness": request.form.get("brightness", 0),
        "contrast": request.form.get("contrast", 100),
        "gamma": request.form.get("gamma", 100),
        "black_level": request.form.get("black_level", 0),
        "white_level": request.form.get("white_level", 255),
        "local_contrast": request.form.get("local_contrast", 3),
        "blur": request.form.get("blur", 1),
        "tone": request.form.get("tone", 10),
        "shadows": request.form.get("shadows", 0),
        "highlights": request.form.get("highlights", 0),
        "sharp": request.form.get("sharp", 0),
        "sharp2": request.form.get("sharp2", 0)
    }

    out_img = process_image_cv(img_bgr, params)
    if out_img is None:
        return jsonify({"error": "Processing failed"}), 500

    # encode to PNG and send
    is_success, buffer = cv2.imencode(".png", out_img)
    if not is_success:
        return jsonify({"error": "Encoding failed"}), 500
    io_buf = io.BytesIO(buffer.tobytes())
    return send_file(io_buf, mimetype="image/png")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug, host="0.0.0.0", port=port)
