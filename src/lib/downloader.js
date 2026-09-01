export async function fetchImageBlob(url) {
  // Try direct fetch. If CORS fails, fall back to a proxy.
  try {
    const res = await fetch(url, { mode: 'cors' });
    if (res.ok) return await res.blob();
  } catch (e) {
    // CORS error or network error, fallback to proxy
    console.log("Direct fetch failed, trying proxy for", url);
  }

  // Free CORS proxy
  const proxyUrl = `https://corsproxy.io/?${encodeURIComponent(url)}`;
  const res = await fetch(proxyUrl);
  if (!res.ok) throw new Error(`Failed to fetch image: ${res.statusText}`);
  return await res.blob();
}

export function saveBlobAsFile(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
