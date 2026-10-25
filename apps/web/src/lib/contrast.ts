/**
 * WCAG 2.1 relative luminance and contrast ratio calculator.
 */

function hexToRgb(hex: string): [number, number, number] {
  const clean = hex.replace("#", "").trim();
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

function getChannelLuminance(channel: number): number {
  const c = channel / 255.0;
  return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
}

export function getRelativeLuminance(hex: string): number {
  const [r, g, b] = hexToRgb(hex);
  return (
    0.2126 * getChannelLuminance(r) +
    0.7152 * getChannelLuminance(g) +
    0.0722 * getChannelLuminance(b)
  );
}

export interface ContrastResult {
  ratio: number;
  ratioFormatted: string;
  passesAA: boolean;
  passesAAA: boolean;
  level: "fail" | "AA" | "AAA";
}

export function checkContrast(foregroundHex: string, backgroundHex: string): ContrastResult {
  const l1 = getRelativeLuminance(foregroundHex);
  const l2 = getRelativeLuminance(backgroundHex);

  const lighter = Math.max(l1, l2);
  const darker = Math.min(l1, l2);

  const ratio = (lighter + 0.05) / (darker + 0.05);
  const passesAA = ratio >= 4.5;
  const passesAAA = ratio >= 7.0;

  let level: "fail" | "AA" | "AAA" = "fail";
  if (passesAAA) level = "AAA";
  else if (passesAA) level = "AA";

  return {
    ratio,
    ratioFormatted: `${ratio.toFixed(1)}:1`,
    passesAA,
    passesAAA,
    level,
  };
}
