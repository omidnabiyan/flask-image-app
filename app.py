from flask import Flask, request, send_file, render_template_string
from PIL import Image
import io
import os

app = Flask(__name__)

HTML = """
<!doctype html>
<title>تست آپلود و تبدیل تصویر</title>
<h1>یک تصویر انتخاب کن</h1>
<form method=post enctype=multipart/form-data>
  <input type=file name=file accept="image/*">
  <input type=submit value="پردازش">
</form>
"""

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        f = request.files.get("file")
        if not f:
            return "هیچ فایلی انتخاب نشده", 400
        img = Image.open(f.stream).convert("L")  # سیاه‌وسفید
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return send_file(buf, mimetype="image/png", as_attachment=True, download_name="gray.png")
    return render_template_string(HTML)

if __name__ == "__main__":
    # برای محیط توسعه یا زمانی که Render متغیر PORT می‌دهد
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
