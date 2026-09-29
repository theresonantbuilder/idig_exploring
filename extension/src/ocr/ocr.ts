import * as Tesseract from 'tesseract.js';

// SPEC.md §4.6: Tesseract.js v5, everything local (worker/core/lang all vendored into
// public/ocr/ and exposed via manifest.json's web_accessible_resources) — Manifest V3
// forbids loading remote code, so nothing here can come from a CDN.

export interface OcrResult {
  text: string;
  confidence: number;
}

let workerPromise: Promise<Tesseract.Worker> | null = null;

async function getWorker(): Promise<Tesseract.Worker> {
  if (!workerPromise) {
    workerPromise = Tesseract.createWorker('eng', Tesseract.OEM.LSTM_ONLY, {
      workerPath: chrome.runtime.getURL('ocr/worker.min.js'),
      corePath: chrome.runtime.getURL('ocr/tesseract-core-simd-lstm.wasm.js'),
      langPath: chrome.runtime.getURL('ocr/'),
      gzip: true,
      // Default wraps workerPath in a blob: URL and importScripts()s the real path from
      // inside it — MV3's worker CSP rejects that (blob: -> chrome-extension:// import is
      // treated as a different, disallowed context). Loading the script directly works.
      workerBlobURL: false,
    }).then(async (worker) => {
      await worker.setParameters({ tessedit_pageseg_mode: Tesseract.PSM.SINGLE_BLOCK });
      return worker;
    });
  }
  return workerPromise;
}

// Upscales small crops so text is at least ~40px tall, then converts to grayscale —
// both measurably help Tesseract on small, low-contrast headline text.
function preprocess(dataUrl: string): Promise<string> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      const MIN_HEIGHT = 40;
      const scale = img.height > 0 && img.height < MIN_HEIGHT ? MIN_HEIGHT / img.height : 1;
      const canvas = document.createElement('canvas');
      canvas.width = Math.max(1, Math.round(img.width * scale));
      canvas.height = Math.max(1, Math.round(img.height * scale));
      const ctx = canvas.getContext('2d');
      if (!ctx) return reject(new Error('2D canvas context unavailable'));
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
      const d = imageData.data;
      for (let i = 0; i < d.length; i += 4) {
        const gray = 0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2];
        d[i] = d[i + 1] = d[i + 2] = gray;
      }
      ctx.putImageData(imageData, 0, 0);
      resolve(canvas.toDataURL('image/png'));
    };
    img.onerror = () => reject(new Error('Failed to load image for OCR preprocessing'));
    img.src = dataUrl;
  });
}

/** The interface the rest of the extension uses, so the engine can be swapped later. */
export async function recognize(image: string): Promise<OcrResult> {
  const processed = await preprocess(image);
  const worker = await getWorker();
  const { data } = await worker.recognize(processed);
  return { text: data.text, confidence: data.confidence };
}
