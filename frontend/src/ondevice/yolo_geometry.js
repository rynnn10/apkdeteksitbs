/* Updated: Rabu, 15-07-2026 13:10 WIB | v2.5.0 */
// Pure letterbox/box math, split out from model_loader.js so it's testable without
// tf.js or DOM (see yolo_geometry.test.mjs).

export function letterboxParams(srcW, srcH, target) {
  const scale = Math.min(target / srcW, target / srcH);
  const drawW = Math.round(srcW * scale);
  const drawH = Math.round(srcH * scale);
  return {
    scale,
    drawW,
    drawH,
    padX: (target - drawW) / 2,
    padY: (target - drawH) / 2,
  };
}

export function clamp01(n) {
  return Math.min(Math.max(n, 0), 1);
}

// Maps a YOLO box (in letterboxed-canvas pixel space) back to normalized [0,1]
// coordinates in the original image.
export function mapBoxToOriginal(x1, y1, x2, y2, { scale, padX, padY, srcW, srcH }) {
  return {
    x1: clamp01((x1 - padX) / scale / srcW),
    y1: clamp01((y1 - padY) / scale / srcH),
    x2: clamp01((x2 - padX) / scale / srcW),
    y2: clamp01((y2 - padY) / scale / srcH),
  };
}
