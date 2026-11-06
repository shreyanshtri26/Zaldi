// Zaldi icon set: one hand-tuned family on a 24px grid. Rounded 1.7px strokes, soft corners, no fills, so every
// icon in chat and admin reads as one voice. No icon library is needed.
const PATHS = {
  chat: "M6 4.5h12A2.5 2.5 0 0 1 20.5 7v7.5a2.5 2.5 0 0 1-2.5 2.5h-5.5L8 20.5V17H6a2.5 2.5 0 0 1-2.5-2.5V7A2.5 2.5 0 0 1 6 4.5z",
  dash: "M4.5 4.5h6v7h-6zM13.5 4.5h6v4h-6zM13.5 11.5h6v8h-6zM4.5 14.5h6v5h-6z",
  box: "M12 3.2 4.2 7.4v9.2L12 20.8l7.8-4.2V7.4L12 3.2zM4.4 7.5 12 11.7l7.6-4.2M12 11.7v9",
  doc: "M7.5 3.5h6.8l4.7 4.7V18a2.5 2.5 0 0 1-2.5 2.5H7.5A2.5 2.5 0 0 1 5 18V6a2.5 2.5 0 0 1 2.5-2.5zM14 3.7V8.5h4.6M9 13h6M9 16.5h4",
  msgs: "M4 6.5A2.5 2.5 0 0 1 6.5 4h6A2.5 2.5 0 0 1 15 6.5v3a2.5 2.5 0 0 1-2.5 2.5H9l-3 2.3V12a2 2 0 0 1-2-2zM17.5 9H18a2 2 0 0 1 2 2v4.5a2 2 0 0 1-1.5 1.9V20l-2.8-2.5H12a2 2 0 0 1-1.7-1",
  search: "M10.8 18a7.2 7.2 0 1 0 0-14.4 7.2 7.2 0 0 0 0 14.4zM16 16l4.5 4.5",
  plus: "M12 5v14M5 12h14",
  send: "M12 19V6M6.5 11.5 12 6l5.5 5.5",
  menu: "M4 7h16M4 12h16M4 17h10",
  trash: "M4.5 7h15M9.5 7V4.5h5V7M6.5 7l.8 11.8a1.7 1.7 0 0 0 1.7 1.7h6a1.7 1.7 0 0 0 1.7-1.7L17.5 7M10 11v5.5M14 11v5.5",
  edit: "M4.5 19.5h4L19 9a2.8 2.8 0 0 0-4-4L4.5 15.5v4zM13 7l4 4",
  copy: "M9.5 9h8a2 2 0 0 1 2 2v7.5a2 2 0 0 1-2 2h-8a2 2 0 0 1-2-2V11a2 2 0 0 1 2-2zM15.5 9V6.5a2 2 0 0 0-2-2H6.5a2 2 0 0 0-2 2V14a2 2 0 0 0 2 2h1",
  x: "M6.5 6.5l11 11M17.5 6.5l-11 11",
  list: "M9 6.5h11M9 12h11M9 17.5h11M4.5 6.5h.01M4.5 12h.01M4.5 17.5h.01",
  grid: "M6 4.5h3a1.5 1.5 0 0 1 1.5 1.5v3A1.5 1.5 0 0 1 9 10.5H6A1.5 1.5 0 0 1 4.5 9V6A1.5 1.5 0 0 1 6 4.5zM15 4.5h3A1.5 1.5 0 0 1 19.5 6v3a1.5 1.5 0 0 1-1.5 1.5h-3A1.5 1.5 0 0 1 13.5 9V6A1.5 1.5 0 0 1 15 4.5zM6 13.5h3a1.5 1.5 0 0 1 1.5 1.5v3A1.5 1.5 0 0 1 9 19.5H6A1.5 1.5 0 0 1 4.5 18v-3A1.5 1.5 0 0 1 6 13.5zM15 13.5h3a1.5 1.5 0 0 1 1.5 1.5v3a1.5 1.5 0 0 1-1.5 1.5h-3a1.5 1.5 0 0 1-1.5-1.5v-3a1.5 1.5 0 0 1 1.5-1.5z",
  out: "M9.5 20H6.5A2 2 0 0 1 4.5 18V6a2 2 0 0 1 2-2h3M15.5 8l4 4-4 4M19.5 12h-10",
  check: "M5.5 12.5l4.2 4.2L18.5 8",
  chevron: "M7 10l5 5 5-5",
  chevronRight: "M10 7l5 5-5 5",
  sliders: "M4 7h8M16 7h4M4 17h3M11 17h9M14 4.8a2.2 2.2 0 1 1 0 4.4 2.2 2.2 0 0 1 0-4.4zM9 14.8a2.2 2.2 0 1 1 0 4.4 2.2 2.2 0 0 1 0-4.4z",
  arrow: "M5 12h14M13.5 6.5 19 12l-5.5 5.5",
  shield: "M12 3.2 5.2 5.8v5.5c0 4.3 2.7 7.6 6.8 9.5 4.1-1.9 6.8-5.2 6.8-9.5V5.8L12 3.2zM9 12l2.2 2.2L15.3 10",
  clock: "M3.8 12a8.2 8.2 0 1 0 2.5-5.9M3.8 4.5v4.2h4.2M12 7.8V12l2.8 1.8",
  cart: "M3.5 4.5h2.2l1.9 9.9a1.8 1.8 0 0 0 1.8 1.5h7.3a1.8 1.8 0 0 0 1.8-1.4l1.3-5.7H6.6M10 20h.01M17 20h.01",
  image: "M6 4.5h12A1.5 1.5 0 0 1 19.5 6v12a1.5 1.5 0 0 1-1.5 1.5H6A1.5 1.5 0 0 1 4.5 18V6A1.5 1.5 0 0 1 6 4.5zM9.2 10.2a1.4 1.4 0 1 0 0-2.8 1.4 1.4 0 0 0 0 2.8zM19.5 15l-4.3-4.3L6 19.5",
  // assistant: a four-point spark with a small companion
  bot: "M10.5 3.5 12.2 8l4.5 1.7-4.5 1.7L10.5 16l-1.7-4.6L4.2 9.7 8.8 8zM18 14.5l.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8z",
  thumbUp: "M8 10.5V20H5.5A1.5 1.5 0 0 1 4 18.5v-6A1.5 1.5 0 0 1 5.5 11H8zM8 10.5 11.2 4.2a1.8 1.8 0 0 1 3.3 1.2L14 9.5h4.6a2 2 0 0 1 2 2.4l-1.3 6.5A2 2 0 0 1 17.3 20H8",
  thumbDown: "M8 13.5V4H5.5A1.5 1.5 0 0 0 4 5.5v6A1.5 1.5 0 0 0 5.5 13H8zM8 13.5l3.2 6.3a1.8 1.8 0 0 0 3.3-1.2L14 14.5h4.6a2 2 0 0 0 2-2.4l-1.3-6.5A2 2 0 0 0 17.3 4H8",
  mic: "M12 15.5a3.2 3.2 0 0 0 3.2-3.2V7.2a3.2 3.2 0 0 0-6.4 0v5.1a3.2 3.2 0 0 0 3.2 3.2zM6 11.5a6 6 0 0 0 12 0M12 17.5v3",
};

// Icons an admin may pick for quick-action cards (kept in sync with the server's allowed list).
export const QUICK_ICONS = ["box", "grid", "doc", "shield", "chat", "search", "clock", "bot"];

export default function Icon({ name, size = 18 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      <path d={PATHS[name]} />
    </svg>
  );
}
