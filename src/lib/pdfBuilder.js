import { PDFDocument } from 'pdf-lib';

/**
 * Builds a PDF from an array of Image Data (ArrayBuffer/Blob).
 * Handles JPEG, PNG. WebP isn't natively supported by pdf-lib, so we must
 * draw it to a canvas and export as JPEG first.
 */
export async function buildPdf(imageBlobs, onProgress) {
  const pdfDoc = await PDFDocument.create();

  for (let i = 0; i < imageBlobs.length; i++) {
    onProgress(i + 1, imageBlobs.length);
    const blob = imageBlobs[i];
    let imgData = await blob.arrayBuffer();

    // If WebP or Unknown, convert to JPEG via Canvas
    if (blob.type.includes('webp') || !['image/jpeg', 'image/png'].includes(blob.type)) {
      imgData = await convertToJpeg(blob);
    }

    let pdfImage;
    try {
      // Try JPEG first
      pdfImage = await pdfDoc.embedJpg(imgData);
    } catch (e) {
      try {
        // Fallback to PNG
        pdfImage = await pdfDoc.embedPng(imgData);
      } catch (e2) {
        console.error(`Failed to embed image ${i}:`, e2);
        continue; // Skip this page if both fail
      }
    }

    const { width, height } = pdfImage.scale(1);
    const page = pdfDoc.addPage([width, height]);
    page.drawImage(pdfImage, {
      x: 0,
      y: 0,
      width,
      height,
    });
  }

  const pdfBytes = await pdfDoc.save();
  return new Blob([pdfBytes], { type: 'application/pdf' });
}

function convertToJpeg(blob) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(blob);
    const img = new Image();
    img.onload = () => {
      const canvas = document.createElement('canvas');
      canvas.width = img.naturalWidth;
      canvas.height = img.naturalHeight;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(img, 0, 0);
      canvas.toBlob((outBlob) => {
        URL.revokeObjectURL(url);
        if (outBlob) {
          outBlob.arrayBuffer().then(resolve).catch(reject);
        } else {
          reject(new Error("Canvas toBlob failed"));
        }
      }, 'image/jpeg', 0.95);
    };
    img.onerror = (e) => {
      URL.revokeObjectURL(url);
      reject(e);
    };
    img.src = url;
  });
}
