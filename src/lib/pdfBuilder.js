/**
 * Opens a new print window with all images laid out page-by-page
 * and triggers the native browser print/save-as-PDF dialog.
 *
 * This completely bypasses CORS because <img> tags load cross-origin
 * images freely — only fetch() is blocked by CORS.
 */
export function printImagesToPdf(imageUrls, title = 'Notes') {
  return new Promise((resolve, reject) => {
    const printWindow = window.open('', '_blank', 'width=900,height=700');
    if (!printWindow) {
      reject(new Error('Popup blocked! Please allow pop-ups for this site and try again.'));
      return;
    }

    const pagesHtml = imageUrls
      .map((url, i) => `<div class="page" id="p${i}"><img src="${url}" alt="Page ${i + 1}" /></div>`)
      .join('');

    printWindow.document.write(`<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>${title}</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    html, body { background: white; }
    .loading {
      position: fixed; inset: 0;
      display: flex; flex-direction: column; align-items: center; justify-content: center;
      background: #0e0d1a; color: #a78bfa; font-family: sans-serif; gap: 16px;
      z-index: 999;
    }
    .bar-wrap { width: 280px; height: 6px; background: #2e2c4a; border-radius: 3px; overflow: hidden; }
    .bar { height: 100%; background: #7c5cbf; border-radius: 3px; transition: width 0.3s; }
    .page {
      width: 100%; min-height: 100vh;
      display: flex; align-items: center; justify-content: center;
      page-break-after: always; break-after: page;
    }
    .page:last-child { page-break-after: auto; break-after: auto; }
    img { max-width: 100%; max-height: 100vh; object-fit: contain; display: block; }
    @media print {
      .loading { display: none !important; }
      .page { height: 100vh; page-break-after: always; break-after: page; }
    }
  </style>
</head>
<body>
  <div class="loading" id="loader">
    <div style="font-size:18px;font-weight:bold;">📄 Loading images for PDF…</div>
    <div class="bar-wrap"><div class="bar" id="bar" style="width:0%"></div></div>
    <div id="count" style="font-size:13px;color:#94a3b8;">0 / ${imageUrls.length}</div>
    <div style="font-size:12px;color:#64748b;margin-top:8px;">Print dialog will open automatically when ready.</div>
  </div>
  ${pagesHtml}
  <script>
    var loaded = 0;
    var total = ${imageUrls.length};
    var bar = document.getElementById('bar');
    var count = document.getElementById('count');
    var loader = document.getElementById('loader');

    function tick() {
      loaded++;
      var pct = Math.round(loaded / total * 100);
      if (bar) bar.style.width = pct + '%';
      if (count) count.textContent = loaded + ' / ' + total;
      if (loaded >= total) {
        setTimeout(function() {
          if (loader) loader.style.display = 'none';
          window.print();
        }, 600);
      }
    }

    document.querySelectorAll('img').forEach(function(img) {
      if (img.complete) { tick(); }
      else { img.onload = tick; img.onerror = tick; }
    });

    if (total === 0) window.print();
  </script>
</body>
</html>`);
    printWindow.document.close();
    resolve();
  });
}
