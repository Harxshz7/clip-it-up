import test from 'node:test';
import assert from 'node:assert/strict';

// 1. WCAG 2.1 Contrast Calculation Logic
function hexToRgb(hex) {
  const clean = hex.replace('#', '').trim();
  if (clean.length === 3) {
    const r = parseInt(clean[0] + clean[0], 16);
    const g = parseInt(clean[1] + clean[1], 16);
    const b = parseInt(clean[2] + clean[2], 16);
    return [r, g, b];
  }
  if (clean.length === 6) {
    const r = parseInt(clean.substring(0, 2), 16);
    const g = parseInt(clean.substring(2, 4), 16);
    const b = parseInt(clean.substring(4, 6), 16);
    return [r, g, b];
  }
  return [255, 255, 255];
}

function getChannelLuminance(channel) {
  const c = channel / 255.0;
  return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
}

function getRelativeLuminance(hex) {
  const [r, g, b] = hexToRgb(hex);
  return 0.2126 * getChannelLuminance(r) + 0.7152 * getChannelLuminance(g) + 0.0722 * getChannelLuminance(b);
}

function checkContrast(foregroundHex, backgroundHex) {
  const l1 = getRelativeLuminance(foregroundHex);
  const l2 = getRelativeLuminance(backgroundHex);
  const lighter = Math.max(l1, l2);
  const darker = Math.min(l1, l2);
  const ratio = (lighter + 0.05) / (darker + 0.05);
  const passesAA = ratio >= 4.5;
  const passesAAA = ratio >= 7.0;
  let level = 'fail';
  if (passesAAA) level = 'AAA';
  else if (passesAA) level = 'AA';
  return { ratio, ratioFormatted: `${ratio.toFixed(1)}:1`, passesAA, passesAAA, level };
}

test('WCAG 2.1 contrast correctly passes black on white with 21:1 ratio (AAA)', () => {
  const res = checkContrast('#000000', '#ffffff');
  assert.equal(res.level, 'AAA');
  assert.ok(res.ratio >= 20.0);
  assert.ok(res.passesAA);
  assert.ok(res.passesAAA);
});

test('WCAG 2.1 contrast correctly flags low contrast colors as fail', () => {
  const res = checkContrast('#888888', '#999999');
  assert.equal(res.level, 'fail');
  assert.ok(!res.passesAA);
  assert.ok(!res.passesAAA);
  assert.ok(res.ratio < 4.5);
});

test('WCAG 2.1 contrast correctly evaluates yellow primary on black background as AAA', () => {
  const res = checkContrast('#FFE500', '#000000');
  assert.equal(res.level, 'AAA');
  assert.ok(res.passesAA);
  assert.ok(res.passesAAA);
});

// 2. Safe zone bounding box clamps (9:16 vertical video)
function clampToSafeZone(pos, marginPct = { top: 12, bottom: 20, left: 8, right: 8 }) {
  let x = pos.x;
  let y = pos.y;
  if (x < marginPct.left) x = marginPct.left;
  if (x > 100 - marginPct.right) x = 100 - marginPct.right;
  if (y < marginPct.top) y = marginPct.top;
  if (y > 100 - marginPct.bottom) y = 100 - marginPct.bottom;
  return { x, y };
}

test('Safe zone placement clamps out-of-bounds logo coordinates', () => {
  // TikTok safe zone: top 12%, bottom 20%, sides 8%
  const tooHigh = clampToSafeZone({ x: 50, y: 5 });
  assert.equal(tooHigh.y, 12);

  const tooLow = clampToSafeZone({ x: 50, y: 95 });
  assert.equal(tooLow.y, 80);

  const tooFarRight = clampToSafeZone({ x: 98, y: 50 });
  assert.equal(tooFarRight.x, 92);

  const valid = clampToSafeZone({ x: 20, y: 25 });
  assert.equal(valid.x, 20);
  assert.equal(valid.y, 25);
});

// 3. Variant set baseline inclusion and deduplication
function buildVariants(baseline, candidates, limit = 4) {
  const result = [{ ...baseline, label: 'Variant A (Baseline)' }];
  const seenKeys = new Set([`${baseline.hook_text}::${baseline.caption_style_key}::${baseline.cta_text}`]);

  for (const c of candidates) {
    if (result.length >= limit) break;
    const key = `${c.hook_text}::${c.caption_style_key}::${c.cta_text}`;
    if (!seenKeys.has(key)) {
      seenKeys.add(key);
      const label = `Variant ${String.fromCharCode(65 + result.length)}`;
      result.push({ ...c, label });
    }
  }
  return result;
}

test('Auto-variants generation always includes Variant A baseline and deduplicates', () => {
  const baseline = { hook_text: 'Original Hook', caption_style_key: 'bold_pop', cta_text: 'Follow for more' };
  const candidates = [
    { hook_text: 'Original Hook', caption_style_key: 'bold_pop', cta_text: 'Follow for more' }, // Duplicate
    { hook_text: 'Hook 2', caption_style_key: 'bold_pop', cta_text: 'Follow for more' },
    { hook_text: 'Hook 3', caption_style_key: 'cinematic', cta_text: 'Share this now' },
    { hook_text: 'Hook 4', caption_style_key: 'minimal', cta_text: 'Follow for more' },
    { hook_text: 'Hook 5', caption_style_key: 'karaoke', cta_text: 'Save for later' },
  ];

  const variants = buildVariants(baseline, candidates, 4);
  assert.equal(variants.length, 4);
  assert.equal(variants[0].label, 'Variant A (Baseline)');
  assert.equal(variants[0].hook_text, 'Original Hook');
  assert.equal(variants[1].label, 'Variant B');
  assert.equal(variants[1].hook_text, 'Hook 2');
  assert.equal(variants[2].label, 'Variant C');
  assert.equal(variants[2].hook_text, 'Hook 3');
  assert.equal(variants[3].label, 'Variant D');
  assert.equal(variants[3].hook_text, 'Hook 4');
});
