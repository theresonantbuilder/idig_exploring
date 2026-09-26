import type { SelectionMessage, SelectionRect } from '../types';

/**
 * Converts a CSS-pixel selection into bitmap pixels and clamps it to the bitmap.
 * devicePixelRatio already includes page zoom (SPEC §4.4).
 */
export function toBitmapRect(
  rect: SelectionRect,
  devicePixelRatio: number,
  bitmap: { width: number; height: number },
): SelectionRect {
  const left = Math.max(0, Math.floor(rect.x * devicePixelRatio));
  const top = Math.max(0, Math.floor(rect.y * devicePixelRatio));
  const right = Math.min(bitmap.width, Math.ceil((rect.x + rect.width) * devicePixelRatio));
  const bottom = Math.min(bitmap.height, Math.ceil((rect.y + rect.height) * devicePixelRatio));
  return { x: left, y: top, width: Math.max(0, right - left), height: Math.max(0, bottom - top) };
}

/**
 * Crops the screenshot to the selection and returns only the crop. The full
 * screenshot never leaves this function (SPEC D9).
 */
export async function cropScreenshot(screenshot: string, selection: SelectionMessage): Promise<string> {
  const bitmap = await createImageBitmap(await (await fetch(screenshot)).blob());
  try {
    const expectedWidth = selection.viewport.width * selection.devicePixelRatio;
    if (Math.abs(bitmap.width - expectedWidth) / expectedWidth > 0.02) {
      // Useful during the Phase A gate check: the crop may be offset if this fires.
      console.warn('iDIG: screenshot width does not match viewport × DPR', {
        bitmap: bitmap.width,
        expected: expectedWidth,
      });
    }

    const area = toBitmapRect(selection.rect, selection.devicePixelRatio, bitmap);
    if (area.width < 1 || area.height < 1) throw new Error('Selection is outside the captured area');

    const canvas = new OffscreenCanvas(area.width, area.height);
    const context = canvas.getContext('2d');
    if (!context) throw new Error('No 2D context');
    context.drawImage(bitmap, area.x, area.y, area.width, area.height, 0, 0, area.width, area.height);
    return blobToDataUrl(await canvas.convertToBlob({ type: 'image/png' }));
  } finally {
    bitmap.close();
  }
}

async function blobToDataUrl(blob: Blob): Promise<string> {
  const bytes = new Uint8Array(await blob.arrayBuffer());
  let binary = '';
  for (let i = 0; i < bytes.length; i += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  }
  return `data:${blob.type};base64,${btoa(binary)}`;
}
