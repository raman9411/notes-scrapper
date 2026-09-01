export function extractUrls(htmlString, baseUrl = '') {
  const parser = new DOMParser();
  const doc = parser.parseFromString(htmlString, 'text/html');
  const seen = new Set();
  const urls = [];

  const add = (u) => {
    let clean = u.trim().split(/\s+/)[0];
    if (clean && !clean.includes('data:image')) {
      try {
        const full = baseUrl ? new URL(clean, baseUrl).href : clean;
        if (!seen.has(full)) {
          seen.add(full);
          urls.push(full);
        }
      } catch (e) {
        if (!seen.has(clean)) {
          seen.add(clean);
          urls.push(clean);
        }
      }
    }
  };

  // Strategy 1: Thumbnails
  const thumbs = doc.querySelectorAll('img.spectra-image-gallery__media-thumbnail');
  if (thumbs.length > 0) {
    thumbs.forEach(img => add(img.getAttribute('data-src') || img.getAttribute('src') || ''));
  }

  // Strategy 2: source srcset
  if (urls.length === 0) {
    const wrappers = doc.querySelectorAll('div.spectra-image-gallery__media-wrapper');
    wrappers.forEach(w => {
      const source = w.querySelector('source');
      if (source) {
        const srcset = source.getAttribute('srcset') || '';
        if (srcset) add(srcset.split(',')[0]);
      }
    });
  }

  // Strategy 3: General spectra container scan
  if (urls.length === 0) {
    const containers = doc.querySelectorAll('[class*="spectra-image-gallery"]');
    containers.forEach(c => {
      const imgs = c.querySelectorAll('img');
      imgs.forEach(img => {
        const u = img.getAttribute('data-src') || img.getAttribute('src') || img.getAttribute('data-lazy-src') || img.getAttribute('data-original') || '';
        if (u && !u.includes('data:image')) add(u);
      });
    });
  }

  // Strategy 4: Regex fallback
  if (urls.length === 0) {
    const regex = /https?:\/\/[^\s"'<>]+wp-content\/uploads\/[^\s"'<>]+\.(?:webp|jpg|jpeg|png)/ig;
    let match;
    while ((match = regex.exec(htmlString)) !== null) {
      add(match[0]);
    }
  }

  return urls;
}
