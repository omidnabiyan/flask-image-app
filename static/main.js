const fileInput = document.getElementById('fileInput');
const processBtn = document.getElementById('processBtn');
const previewImg = document.getElementById('previewImg');
const downloadLink = document.getElementById('downloadLink');

function collectParams() {
  const params = {};
  document.querySelectorAll('#sliders input[type="range"]').forEach(r => {
    params[r.dataset.name] = r.value;
  });
  return params;
}

async function processImage() {
  if (!fileInput.files[0]) {
    alert('ابتدا فایل را انتخاب کن');
    return;
  }
  processBtn.disabled = true;
  processBtn.textContent = 'در حال پردازش...';

  const fd = new FormData();
  fd.append('image', fileInput.files[0]);
  const params = collectParams();
  for (const k in params) fd.append(k, params[k]);

  try {
    const resp = await fetch('/process', {
      method: 'POST',
      body: fd
    });
    if (!resp.ok) {
      const j = await resp.json().catch(()=>null);
      alert('خطا: ' + (j && j.error ? j.error : resp.statusText));
      return;
    }
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    previewImg.src = url;
    previewImg.style.display = 'block';

    // لینک دانلود
    downloadLink.href = url;
    downloadLink.download = 'processed.png';
    downloadLink.textContent = 'دانلود تصویر';
    downloadLink.style.display = 'inline-block';
  } catch (err) {
    alert('خطا در ارتباط: ' + err.message);
  } finally {
    processBtn.disabled = false;
    processBtn.textContent = 'پردازش';
  }
}

processBtn.addEventListener('click', processImage);
