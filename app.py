import os
from flask import Flask, render_template, request
from PIL import Image

app = Flask(__name__)
UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/', methods=['GET', 'POST'])
def index():
    processed_image = None
    if request.method == 'POST':
        file = request.files['image']
        if file:
            img_path = os.path.join(UPLOAD_FOLDER, file.filename)
            file.save(img_path)

            # تبدیل به سیاه و سفید
            img = Image.open(img_path).convert('L')
            processed_path = os.path.join(UPLOAD_FOLDER, f'processed_{file.filename}')
            img.save(processed_path)
            
            processed_image = f'uploads/processed_{file.filename}'

    return render_template('index.html', processed_image=processed_image)

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug, host="0.0.0.0", port=port)

