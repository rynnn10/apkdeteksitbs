// Run: node frontend/src/ondevice/yolo_geometry.test.mjs
import assert from "node:assert";
import { letterboxParams, mapBoxToOriginal, clamp01 } from "./yolo_geometry.js";

// Landscape image (1280x720) letterboxed into a 640 square: fits width, pads top/bottom.
{
  const p = letterboxParams(1280, 720, 640);
  assert.strictEqual(p.scale, 0.5);
  assert.strictEqual(p.drawW, 640);
  assert.strictEqual(p.drawH, 360);
  assert.strictEqual(p.padX, 0);
  assert.strictEqual(p.padY, 140);
}

// A box drawn at the letterboxed image's exact edges maps back to the full original frame.
{
  const p = letterboxParams(1280, 720, 640);
  const box = mapBoxToOriginal(0, 140, 640, 500, { ...p, srcW: 1280, srcH: 720 });
  assert.strictEqual(box.x1, 0);
  assert.strictEqual(box.y1, 0);
  assert.strictEqual(box.x2, 1);
  assert.ok(Math.abs(box.y2 - 1) < 1e-9);
}

// Square image needs no padding at all.
{
  const p = letterboxParams(640, 640, 640);
  assert.strictEqual(p.padX, 0);
  assert.strictEqual(p.padY, 0);
  assert.strictEqual(p.scale, 1);
}

// Out-of-range coords get clamped into [0,1], never left dangling.
assert.strictEqual(clamp01(-5), 0);
assert.strictEqual(clamp01(5), 1);
assert.strictEqual(clamp01(0.5), 0.5);

console.log("yolo_geometry: all checks passed");
