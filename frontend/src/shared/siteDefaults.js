// Fallback used until (or if) /api/site-config answers. Mirrors the server defaults, i.e. the original UI.
export const SITE_DEFAULTS = {
  settings: {
    brand_name: "Zaldi",
    tagline: "Fashion assistant",
    welcome_heading: "What are you looking for today?",
    welcome_subtitle: "Ask about sarees, kurtas, sizes, delivery, returns or payments. You can write in English, Hindi or Hinglish.",
    input_placeholder: "Type your message…",
  },
  quickActions: [
    { id: 1, title: "Sarees", subtitle: "Banarasi, Kanjivaram, Mysore silk", message: "Show me Banarasi sarees", icon: "box" },
    { id: 2, title: "Kurtas", subtitle: "Chikankari, block print, silk", message: "Kurtas under Rs. 1500", icon: "grid" },
    { id: 3, title: "Payment", subtitle: "COD, UPI, cards, EMI", message: "Is COD available?", icon: "doc" },
    { id: 4, title: "Returns", subtitle: "7-day returns and refunds", message: "What is the return policy?", icon: "shield" },
  ],
};
