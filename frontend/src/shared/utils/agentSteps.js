// What the assistant did for each route (the API reports `type`: "products" or "chitchat").
// Used by the chat's "Completed" card and the admin transcript timeline.
export const AGENT_STEPS = {
  products: [
    ["Understood the question", "The router classified it as a product or policy question"],
    ["Checked store data", "Searched the product catalogue and store policies"],
    ["Wrote the answer", "Composed a reply from the matching data"],
  ],
  cart: [
    ["Understood the request", "Recognised a cart action"],
    ["Updated your cart", "Checked stock and recalculated prices, shipping and discounts"],
  ],
  checkout: [
    ["Understood the request", "Recognised a checkout request"],
    ["Reviewed your cart", "Nothing is ordered until you confirm"],
  ],
  chitchat: [
    ["Understood the question", "The router classified it as general conversation"],
    ["Wrote the answer", "Replied in a friendly tone without searching store data"],
  ],
};

const LABELS = { products: "Product search", cart: "Cart", checkout: "Checkout", chitchat: "Conversation" };
export const routeLabel = (route) => LABELS[route] || "Conversation";
