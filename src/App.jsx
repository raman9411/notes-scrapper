import React, { useState, useRef, useEffect } from 'react';
import { UploadCloud, Link as LinkIcon, Download, FileText, Trash2, CheckSquare, Square, Check, AlertCircle, Loader2, Printer } from 'lucide-react';
import { extractUrls } from './lib/scraper';
import { fetchImageBlob, saveBlobAsFile } from './lib/downloader';
import { printImagesToPdf } from './lib/pdfBuilder';

export default function App() {
  const [urls, setUrls] = useState([]);
  const [selected, setSelected] = useState(new Set());
  const [logs, setLogs] = useState([]);
  const [isDragging, setIsDragging] = useState(false);
  const [urlInput, setUrlInput] = useState('');
  const [status, setStatus] = useState('idle'); // idle, fetching, downloading, building-pdf
  const [progress, setProgress] = useState({ current: 0, total: 0 });
  const [makePdf, setMakePdf] = useState(false);
  const logEndRef = useRef(null);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const log = (msg, type = 'info') => {
    setLogs(prev => [...prev, { time: new Date().toLocaleTimeString(), msg, type }]);
  };

  const clearState = () => {
    setUrls([]);
    setSelected(new Set());
    setStatus('idle');
    setProgress({ current: 0, total: 0 });
    log('Cleared session.', 'dim');
  };

  const handleDrop = async (e) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (!file) return;
    
    log(`📂 Reading local file: ${file.name}`, 'dim');
    const text = await file.text();
    processHtml(text, 'local');
  };

  const handleUrlFetch = async () => {
    if (!urlInput) return;
    setStatus('fetching');
    log(`🌐 Fetching: ${urlInput}`, 'dim');
    try {
      const proxyUrl = `https://corsproxy.io/?${encodeURIComponent(urlInput)}`;
      const res = await fetch(proxyUrl);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const text = await res.text();
      processHtml(text, urlInput);
    } catch (e) {
      log(`❌ Fetch failed: ${e.message}`, 'error');
      setStatus('idle');
    }
  };

  const processHtml = (html, sourceUrl) => {
    log('🔎 Extracting image URLs...', 'dim');
    const extracted = extractUrls(html, sourceUrl === 'local' ? '' : sourceUrl);
    
    if (extracted.length === 0) {
      log('⚠️ No images found.', 'warning');
      setStatus('idle');
      return;
    }

    log(`✅ Found ${extracted.length} images!`, 'success');
    setUrls(extracted);
    setSelected(new Set(extracted.map((_, i) => i)));
    setStatus('idle');
  };

  const toggleSelect = (i) => {
    const next = new Set(selected);
    if (next.has(i)) next.delete(i);
    else next.add(i);
    setSelected(next);
  };

  const toggleSelectAll = () => {
    if (selected.size === urls.length) setSelected(new Set());
    else setSelected(new Set(urls.map((_, i) => i)));
  };

  const startDownload = async () => {
    if (selected.size === 0) return;
    const selectedIndices = Array.from(selected).sort((a, b) => a - b);
    const total = selectedIndices.length;

    // ── PDF PATH: open print window, zero CORS issues ──────────────────────
    if (makePdf) {
      const selectedUrls = selectedIndices.map(i => urls[i]);
      log(`▶ Opening print view for ${total} pages…`, 'info');
      log('  When the dialog opens, choose “Save as PDF” as the destination.', 'dim');
      try {
        await printImagesToPdf(selectedUrls, 'Notes');
        log('✅ Print dialog opened — select “Save as PDF” to save.', 'success');
      } catch (e) {
        log(`❌ ${e.message}`, 'error');
      }
      return;
    }

    // ── DOWNLOAD IMAGES PATH ────────────────────────────────────────────────
    setStatus('downloading');
    setProgress({ current: 0, total });
    log('▶ Starting download…', 'info');

    let success = 0;
    let failed = 0;

    for (let i = 0; i < total; i++) {
      const idx = selectedIndices[i];
      const url = urls[idx];
      try {
        const blob = await fetchImageBlob(url);
        const ext = url.split('.').pop().split('?')[0].toLowerCase();
        const safeExt = ['jpg', 'jpeg', 'png', 'webp'].includes(ext) ? ext : 'webp';
        saveBlobAsFile(blob, `page_${(idx + 1).toString().padStart(3, '0')}.${safeExt}`);
        success++;
        log(`  ✅ [${i + 1}/${total}] Downloaded page ${idx + 1}`, 'success');
      } catch (e) {
        failed++;
        log(`  ❌ [${i + 1}/${total}] Failed page ${idx + 1}: ${e.message}`, 'error');
      }
      setProgress({ current: i + 1, total });
    }

    setStatus('idle');
    log(`📊 Done — ✅ ${success} saved  ❌ ${failed} failed`, 'info');
  };

  return (
    <div className="max-w-4xl mx-auto p-4 space-y-6">
      <div className="bg-card rounded-xl border border-border-color overflow-hidden shadow-xl">
        <div className="h-1 bg-gradient-to-r from-accent to-accent-lt w-full" />
        <div className="p-6 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="bg-accent/20 p-2 rounded-lg text-accent-lt">
              <UploadCloud size={24} />
            </div>
            <div>
              <h1 className="text-xl font-bold text-white">Notes Scrapper Web</h1>
              <p className="text-sm text-slate-400">boardstudy.in • WordPress Spectra</p>
            </div>
          </div>
        </div>
      </div>

      {urls.length === 0 && (
        <div className="grid md:grid-cols-2 gap-4">
          <div 
            onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={handleDrop}
            className={`
              flex flex-col items-center justify-center p-8 rounded-xl border-2 border-dashed transition-all cursor-pointer
              ${isDragging ? 'border-accent bg-accent/10' : 'border-border-color bg-surface hover:border-accent-lt/50'}
            `}
          >
            <FileText size={32} className={isDragging ? 'text-accent-lt mb-3' : 'text-slate-500 mb-3'} />
            <h3 className="font-semibold text-white">Drag & Drop HTML File</h3>
            <p className="text-sm text-slate-400 mt-1 text-center">Save page as HTML and drop here to bypass CORS restrictions.</p>
          </div>

          <div className="flex flex-col justify-center p-6 rounded-xl border border-border-color bg-surface">
            <h3 className="font-semibold text-white mb-2 flex items-center gap-2">
              <LinkIcon size={16} /> Paste Page URL
            </h3>
            <div className="flex gap-2">
              <input 
                type="text" 
                value={urlInput}
                onChange={e => setUrlInput(e.target.value)}
                placeholder="https://boardstudy.in/..." 
                className="flex-1 bg-bg border border-border-color rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-accent"
              />
              <button 
                onClick={handleUrlFetch}
                disabled={status !== 'idle'}
                className="bg-accent hover:bg-accent-lt text-white px-4 py-2 rounded-lg text-sm font-semibold transition-colors disabled:opacity-50"
              >
                {status === 'fetching' ? <Loader2 size={16} className="animate-spin" /> : 'Fetch'}
              </button>
            </div>
            <p className="text-xs text-slate-500 mt-3 flex items-start gap-1">
              <AlertCircle size={14} className="shrink-0" />
              Uses a public proxy. If it fails, use the Drag & Drop method.
            </p>
          </div>
        </div>
      )}

      {urls.length > 0 && (
        <div className="grid md:grid-cols-3 gap-6">
          <div className="md:col-span-2 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="font-bold text-white">Found {urls.length} Images</h2>
              <button onClick={toggleSelectAll} className="text-sm text-accent-lt hover:text-white flex items-center gap-1">
                {selected.size === urls.length ? <CheckSquare size={16} /> : <Square size={16} />}
                Select All
              </button>
            </div>
            
            <div className="grid grid-cols-3 sm:grid-cols-4 gap-3 max-h-[500px] overflow-y-auto pr-2 custom-scrollbar">
              {urls.map((u, i) => {
                const isSel = selected.has(i);
                return (
                  <div 
                    key={i} 
                    onClick={() => toggleSelect(i)}
                    className={`relative aspect-[3/4] rounded-lg overflow-hidden cursor-pointer border-2 transition-all ${isSel ? 'border-accent ring-2 ring-accent/30' : 'border-transparent hover:border-slate-600'}`}
                  >
                    <img src={u} loading="lazy" className="w-full h-full object-cover" />
                    <div className="absolute top-2 right-2 bg-black/50 rounded p-1">
                      {isSel && <Check size={14} className="text-accent-lt" />}
                    </div>
                    <div className="absolute bottom-0 inset-x-0 bg-gradient-to-t from-black/80 to-transparent p-2 text-xs font-mono">
                      {i + 1}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="space-y-4">
            <div className="bg-card p-5 rounded-xl border border-border-color space-y-4">
              <div 
                onClick={() => setMakePdf(!makePdf)}
                className="flex items-start gap-3 p-3 rounded-lg border border-border-color cursor-pointer hover:bg-surface transition-colors"
              >
                <div className={`w-5 h-5 rounded flex items-center justify-center border shrink-0 mt-0.5 ${makePdf ? 'bg-green-500 border-green-500' : 'border-slate-500'}`}>
                  {makePdf && <Check size={14} className="text-white" />}
                </div>
                <div className="text-sm">
                  <div className="font-semibold text-white">Combine into PDF</div>
                  <div className="text-slate-400 text-xs mt-0.5">Opens browser print dialog → Save&nbsp;as&nbsp;PDF. Works offline, no CORS issues.</div>
                </div>
              </div>

              <button 
                onClick={startDownload}
                disabled={status !== 'idle' || selected.size === 0}
                className="w-full bg-accent hover:bg-accent-lt text-white py-3 rounded-lg font-bold flex items-center justify-center gap-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {status !== 'idle'
                  ? <Loader2 size={18} className="animate-spin" />
                  : makePdf ? <Printer size={18} /> : <Download size={18} />}
                {status !== 'idle'
                  ? 'Processing…'
                  : makePdf
                    ? `Open as PDF (${selected.size} pages)`
                    : `Download ${selected.size} Files`}
              </button>

              <button 
                onClick={clearState}
                disabled={status !== 'idle'}
                className="w-full bg-surface hover:bg-border-color text-slate-300 py-2 rounded-lg font-semibold flex items-center justify-center gap-2 transition-colors disabled:opacity-50"
              >
                <Trash2 size={16} /> Clear Session
              </button>
            </div>

            {status !== 'idle' && (
              <div className="bg-card p-4 rounded-xl border border-border-color">
                <div className="flex justify-between text-xs text-slate-400 mb-2">
                  <span>{status === 'building-pdf' ? 'Building PDF...' : 'Downloading...'}</span>
                  <span>{progress.current} / {progress.total}</span>
                </div>
                <div className="h-2 bg-surface rounded-full overflow-hidden">
                  <div 
                    className="h-full bg-accent transition-all duration-300"
                    style={{ width: `${progress.total > 0 ? (progress.current / progress.total) * 100 : 0}%` }}
                  />
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      <div className="bg-surface rounded-xl border border-border-color overflow-hidden flex flex-col h-48">
        <div className="bg-card px-4 py-2 border-b border-border-color text-xs font-semibold text-slate-400">
          Console Output
        </div>
        <div className="p-4 flex-1 overflow-y-auto font-mono text-xs space-y-1 custom-scrollbar">
          {logs.map((l, i) => (
            <div key={i} className={`
              ${l.type === 'error' ? 'text-red-400' : ''}
              ${l.type === 'success' ? 'text-green-400' : ''}
              ${l.type === 'warning' ? 'text-amber-400' : ''}
              ${l.type === 'info' ? 'text-blue-400' : ''}
              ${l.type === 'dim' ? 'text-slate-500' : ''}
            `}>
              <span className="text-slate-600 mr-2">[{l.time}]</span>
              {l.msg}
            </div>
          ))}
          <div ref={logEndRef} />
        </div>
      </div>
    </div>
  );
}
