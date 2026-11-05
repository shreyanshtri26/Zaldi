/** Design tokens from the Zaldi AI brief. */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        app: "#0B0C0E", surface: "#141517", surface2: "#191B1E", raised: "#202226",
        ink: "#F4F5F7", ink2: "#9299A5", mute: "#68717E", line: "#292C31",
        primary: { DEFAULT: "#91CBEA", hover: "#A8D9F2" },
        ok: "#36C98A", warn: "#E5A04D", bad: "#E16B70", info: "#79B8E7",
      },
      fontFamily: { sans: ["Inter", "system-ui", "sans-serif"] },
      borderRadius: { card: "12px" },
    },
  },
  plugins: [],
};
