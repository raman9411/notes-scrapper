export async function fetchImageBlob(url) {
  // Try direct fetch. If CORS fails, fall back to proxies.
  try {
    const res = await fetch(url, { mode: 'cors' });
    if (res.ok) return await res.blob();
  } catch (e) {
    console.log("Direct fetch failed, trying proxies for", url);
  }

  const proxies = [
    (u) => `https://api.allorigins.win/raw?url=${encodeURIComponent(u)}`,
    (u) => `https://api.codetabs.com/v1/proxy?quest=${encodeURIComponent(u)}`,
    (u) => `https://corsproxy.io/?${encodeURIComponent(u)}`
  ];

  for (const proxyGen of proxies) {
    try {
      const proxyUrl = proxyGen(url);
      const res = await fetch(proxyUrl);
      if (res.ok) return await res.blob();
    } catch (e) {
      console.log("Proxy failed:", e.message);
    }
  }

  throw new Error(`CORS blocked or network error`);
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
