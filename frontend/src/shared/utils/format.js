// Small display helpers shared across views.

// Stable 0-359 hue derived from a string (used for placeholder product thumbnails).
export const hue = (text = "") => [...text].reduce((h, c) => (h * 31 + c.charCodeAt(0)) % 360, 7);

// 1799 -> "Rs. 1,799" (Indian digit grouping).
export const inr = (amount) => "Rs. " + Number(amount).toLocaleString("en-IN");
