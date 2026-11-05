// CMS look settings -> CSS variables. Defaults return {} so the built-in theme is untouched.
import { SITE_DEFAULTS } from "./siteDefaults.js";

export const FONTS = {
  default: ["Default (DM Sans)", null],
  serif: ["Serif (Georgia)", 'Georgia, "Times New Roman", serif'],
  system: ["System", 'system-ui, -apple-system, "Segoe UI", sans-serif'],
  mono: ["Monospace", "ui-monospace, Consolas, monospace"],
};

export const PALETTE = [
  ["color_navy", "Navy", "Dark surfaces, text, logo body"],
  ["color_sky", "Sky", "Buttons, highlights, logo bolt"],
  ["color_blue", "Blue", "Secondary accent, logo back panel"],
  ["color_slate", "Slate", "Muted text, borders, logo side panel"],
  ["color_silver", "Silver", "Light backgrounds and body text"],
];

// Logo mark drawn from the palette, so the header logo and tab icon follow the CMS colours.
export const markSvg = (s) => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="25 12 150 180"><path d="M72 74V58a28 28 0 0 1 56 0v16" fill="none" stroke="${s.color_navy}" stroke-width="8" stroke-linecap="round"/><path d="M45 70h110l10 105q0 10-10 10H45q-10 0-10-10z" fill="${s.color_navy}"/><path d="M45 70h33l-8 115H45q-10 0-10-10z" fill="${s.color_blue}"/><path d="M122 70h33l10 105q0 10-10 10h-25z" fill="${s.color_slate}"/><path d="M109 88 82 131h16l-6 38 28-47h-17z" fill="${s.color_sky}"/></svg>`;
export const markUrl = (s) => `data:image/svg+xml,${encodeURIComponent(markSvg(s))}`;

export function themeVars(s) {
  const d = SITE_DEFAULTS.settings, v = {};
  const changed = PALETTE.some(([k]) => s[k] !== d[k]);
  PALETTE.forEach(([k]) => { if (s[k] !== d[k]) v[`--c-${k.slice(6)}`] = s[k]; });
  if (changed) v["--mark-url"] = `url("${markUrl(s)}")`;
  const font = FONTS[s.font_family]?.[1];
  if (font) v["--font-body"] = v["--font-display"] = font;
  if (s.font_size !== d.font_size) v["--fs"] = `${s.font_size}px`;
  if (s.bar_width !== d.bar_width) v["--bar-w"] = { narrow: "560px", wide: "960px" }[s.bar_width];
  if (s.bar_shape !== d.bar_shape) v["--bar-r"] = { rounded: "12px", square: "4px" }[s.bar_shape];
  return v;
}
