// Writes placeholder toolbar icons (public/icons/icon{16,48,128}.png): a brass
// "i" on a deep-blue rounded square. No dependencies; run with `npm run icons`.
import { deflateSync } from 'node:zlib';
import { writeFileSync, mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const BLUE = [20, 35, 58];
const BRASS = [217, 180, 90];
const SAMPLES = 4; // supersampling per axis, for smooth edges

function insideRoundedSquare(x, y, radius) {
  const cx = Math.min(Math.max(x, radius), 1 - radius);
  const cy = Math.min(Math.max(y, radius), 1 - radius);
  return (x - cx) ** 2 + (y - cy) ** 2 <= radius ** 2;
}

function insideI(x, y) {
  const dot = (x - 0.5) ** 2 + (y - 0.28) ** 2 <= 0.095 ** 2;
  const stem = x >= 0.415 && x <= 0.585 && y >= 0.43 && y <= 0.8;
  return dot || stem;
}

function pixel(px, py, size) {
  let background = 0;
  let glyph = 0;
  for (let sy = 0; sy < SAMPLES; sy++) {
    for (let sx = 0; sx < SAMPLES; sx++) {
      const x = (px + (sx + 0.5) / SAMPLES) / size;
      const y = (py + (sy + 0.5) / SAMPLES) / size;
      if (!insideRoundedSquare(x, y, 0.22)) continue;
      background++;
      if (insideI(x, y)) glyph++;
    }
  }
  const total = SAMPLES * SAMPLES;
  const mix = background ? glyph / background : 0;
  const rgb = BLUE.map((b, i) => Math.round(b + (BRASS[i] - b) * mix));
  return [...rgb, Math.round((background / total) * 255)];
}

const CRC_TABLE = Array.from({ length: 256 }, (_, n) => {
  let c = n;
  for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
  return c >>> 0;
});

function crc32(buffer) {
  let c = 0xffffffff;
  for (const byte of buffer) c = CRC_TABLE[(c ^ byte) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

function chunk(type, data) {
  const length = Buffer.alloc(4);
  length.writeUInt32BE(data.length);
  const body = Buffer.concat([Buffer.from(type, 'ascii'), data]);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(body));
  return Buffer.concat([length, body, crc]);
}

function png(size) {
  const rows = [];
  for (let y = 0; y < size; y++) {
    const row = [0]; // filter: none
    for (let x = 0; x < size; x++) row.push(...pixel(x, y, size));
    rows.push(Buffer.from(row));
  }
  const header = Buffer.alloc(13);
  header.writeUInt32BE(size, 0);
  header.writeUInt32BE(size, 4);
  header[8] = 8; // bit depth
  header[9] = 6; // RGBA
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk('IHDR', header),
    chunk('IDAT', deflateSync(Buffer.concat(rows))),
    chunk('IEND', Buffer.alloc(0)),
  ]);
}

const outDir = fileURLToPath(new URL('../public/icons/', import.meta.url));
mkdirSync(outDir, { recursive: true });
for (const size of [16, 48, 128]) {
  writeFileSync(`${outDir}icon${size}.png`, png(size));
  console.log(`icon${size}.png`);
}
