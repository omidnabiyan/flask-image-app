// main.js — client-side logic
const fileInput = document.getElementById("fileInput");
const previewImg = document.getElementById("previewImg");
const slidersContainer = document.getElementById("sliders");
const enhanceBtn = document.getElementById("enhanceBtn");
const undoBtn = document.getElementById("undoBtn");
const resetBtn = document.getElementById("resetBtn");
const downloadLink = document.getElementById("downloadLink");

// تعریف اسلایدرها (نام فارسی مطابق کد پایتون)
const sliderDefs = [
  { name: "روشنایی", min:-100, max:100, value:0 },
  { name: "کنتراست", min:50, max:300, value:100 },
  { name: "گاما", min:10, max:300, value:100 },
  { name: "سطح سیاه", min:-250, max:250, value:0 },
  { name: "سطح سفید", min:0, max:255, value:255 },
  { name: "Local Contrast", min:1, max:10, value:3 },
  { name: "Blur", min:1, max:50, value:1 },
  { name: "Gamma / Tone Curve", min:5, max:25, value:10 },
  { name: "Shadows", min:-50, max:50, value:0 },
  { name: "Highlights", min:-50, max:50, value:0 },
  // sharp sliders
  { name: "تیزی", min:0, max:300, value:0 },
  { name: "تیزی۲", min:0, max:300, value:0 }
];

const state = {}; // نگه داشتن مقادیر فعلی اسلایدرها

// ساختار DOM اسلایدرها
sliderDefs.forEach(def => {
  const row = document.createElement("div");
  row.className = "slider-row";
  const label = document.createElement("label");
  label.textContent = def.name;
  const input = document.createElement("input");
  input.type = "range";
  input.min = def.min;
  input.max = def.max;
  input.value = def.value;
  input.dataset.name = def.name;
  const valSpan = document.createElement("span");
  valSpan.style.minWidth = "36px";
  valSpan.style.display = "inline-block";
  valSpan.textContent = def.value;

  input.addEventListener("input", () => {
    valSpan.textContent = input.value;
    state[def.name] = input.value;
    schedulePreview();
  });

  row.appendChild(label);
  row.appendChild(input);
  row.appendChild(valSpan);
  slidersContainer.appendChild(row);

  // init state
  state[def.name] = def.value;
});

// debouncing برای جلوگیری از ارسال بیش از حد درخواست‌ها
let previewTimer = null;
function schedulePreview(delay = 180) {
  if (previewTimer) clearTimeout(previewTimer);
  previewTimer = setTimeout(() => {
    updatePreview();
  }, delay);
}

async function uploadFile(file) {
  const fd = new FormData();
  fd.append("image", file);
  try {
    const resp = await fetch("/upload", { method: "POST", body: fd });
    if (!resp.ok) {
      const j = await resp.json().catch(()=>null);
      alert("آپلود ناموفق: " + (j && j.error ? j.error : resp.statusText));
      return false;
    }
    const blob = await resp.blob();
    previewImg.src = URL.createObjectURL(blob);
    // show download link (will hit server /download later)
    downloadLink.style.display = "inline-block";
    downloadLink.href = "/download";
    downloadLink.textContent = "دانلود تصویر";
    return true;
  } catch (err) {
    alert("خطا در آپلود: " + err.message);
    return false;
  }
}

fileInput.addEventListener("change", async (e) => {
  if (!e.target.files || !e.target.files[0]) return;
  await uploadFile(e.target.files[0]);
});

// update preview by posting JSON of state
async function updatePreview() {
  try {
    const resp = await fetch("/update_preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(state)
    });
    if (!resp.ok) {
      const j = await resp.json().catch(()=>null);
      console.error("Preview error", j || resp.statusText);
      return;
    }
    const blob = await resp.blob();
    previewImg.src = URL.createObjectURL(blob);
    // update download link to always point to server-side download endpoint
    downloadLink.style.display = "inline-block";
    downloadLink.href = "/download";
    downloadLink.textContent = "دانلود تصویر";
  } catch (err) {
    console.error("Network error", err);
  }
}

// Enhance — ارسال به /apply تا در history ذخیره شود
enhanceBtn.addEventListener("click", async () => {
  // اعمال مقادیر پیشنهادی مشابه دسکتاپ
  const presets = {
    "کنتراست": 120, "روشنایی": 10, "گاما": 100,
    "سطح سیاه": 0, "سطح سفید": 255,
    "Local Contrast": 5, "Blur": 5, "Gamma / Tone Curve": 12,
    "Shadows": 10, "Highlights": 10, "تیزی": 100, "تیزی۲": 50
  };
  // اعمال به DOM و state
  document.querySelectorAll('#sliders input[type="range"]').forEach(r => {
    if (presets.hasOwnProperty(r.dataset.name)) {
      r.value = presets[r.dataset.name];
      state[r.dataset.name] = r.value;
      r.nextSibling && (r.nextSibling.textContent = r.value); // update span
    }
  });
  // ارسال به سرور و ذخیره در history
  try {
    const resp = await fetch("/apply", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(state)
    });
    if (!resp.ok) {
      const j = await resp.json().catch(()=>null);
      alert("خطا در اعمال: " + (j && j.error ? j.error : resp.statusText));
      return;
    }
    const blob = await resp.blob();
    previewImg.src = URL.createObjectURL(blob);
  } catch (err) {
    alert("خطا: " + err.message);
  }
});

// Undo — فراخوانی endpoint مربوطه
undoBtn.addEventListener("click", async () => {
  try {
    const resp = await fetch("/undo", { method: "POST" });
    if (!resp.ok) {
      const j = await resp.json().catch(()=>null);
      alert("خطا در Undo: " + (j && j.error ? j.error : resp.statusText));
      return;
    }
    const j = await resp.json().catch(()=>null);
    if (j && j.empty) {
      // هیچ عکسی برای نمایش نیست -> بارگذاری اولیه را از سرور بگیر
      previewImg.src = "";
      alert("هیچ حالت ذخیره‌شده‌ای وجود ندارد.");
      return;
    }
    const blob = await resp.blob();
    previewImg.src = URL.createObjectURL(blob);
  } catch (err) {
    console.error(err);
  }
});

// Reset -> بازگرداندن مقادیر پیش‌فرض
resetBtn.addEventListener("click", () => {
  const defaults = {
    "روشنایی": 0, "کنتراست": 100, "گاما": 100,
    "سطح سیاه": 0, "سطح سفید": 255, "Local Contrast": 3,
    "Blur": 1, "Gamma / Tone Curve": 10,
    "Shadows": 0, "Highlights": 0, "تیزی": 0, "تیزی۲": 0
  };
  document.querySelectorAll('#sliders input[type="range"]').forEach(r => {
    if (defaults.hasOwnProperty(r.dataset.name)) {
      r.value = defaults[r.dataset.name];
      state[r.dataset.name] = r.value;
      r.nextSibling && (r.nextSibling.textContent = r.value);
    }
  });
  schedulePreview(50);
});
