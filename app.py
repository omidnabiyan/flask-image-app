from flask import Flask, render_template, request, send_file
import cv2, numpy as np
from io import BytesIO

app = Flask(__name__)

# نمونه تصویر اولیه
cv_img = cv2.imread('static/sample.jpg', cv2.IMREAD_COLOR)

@app.route("/", methods=["GET", "POST"])
def index():
    return render_template("index.html")

@app.route("/update_preview", methods=["POST"])
def update_preview():
    global cv_img
    data = request.json
    if cv_img is None:
        return "No image", 400

    # --- پردازش تصویر ---
    img = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)

    # روشنایی / کنتراست
    alpha = float(data.get("contrast",100))/100.0
    beta = int(data.get("brightness",0))
    img = cv2.convertScaleAbs(img, alpha=alpha, beta=beta)

    # گاما / تون
    gamma = float(data.get("gamma",100))/100.0
    if abs(gamma-1.0) > 1e-6:
        inv_gamma = 1.0 / gamma
        table = (np.linspace(0,1,256)**inv_gamma)*255
        img = cv2.LUT(img.astype(np.uint8), table.astype(np.uint8))

    # blur
    blur_val = int(data.get("blur",1))
    if blur_val>1:
        if blur_val%2==0: blur_val+=1
        img = cv2.GaussianBlur(img,(blur_val,blur_val),0)

    # sharpen
    sharp_val = float(data.get("sharp",0))/100.0
    if sharp_val>0:
        kernel = np.array([[0,-1,0],[-1,1+sharp_val*5,-1],[0,-1,0]],dtype=np.float32)
        img = cv2.filter2D(img,-1,kernel)

    # Shadows / Highlights (اختیاری)
    shadows_val = float(data.get("shadows",0))/100.0
    highlights_val = float(data.get("highlights",0))/100.0
    img_f = img.astype(np.float32)/255.0
    if shadows_val!=0:
        mask = img_f<0.5
        img_f = np.where(mask, np.clip(img_f + shadows_val*(0.5-img_f),0,1), img_f)
    if highlights_val!=0:
        mask = img_f>=0.5
        img_f = np.where(mask, np.clip(img_f + highlights_val*(img_f-0.5),0,1), img_f)
    img = (img_f*255).astype(np.uint8)

    # تبدیل به JPEG برای ارسال
    _, buffer = cv2.imencode(".jpg", img)
    return send_file(BytesIO(buffer.tobytes()), mimetype="image/jpeg")

if __name__=="__main__":
    app.run(debug=True)
