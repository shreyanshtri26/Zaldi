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

const LABELS = { products: "Product search", cart: "Cart", checkout: "Checkout", chitchat: "Conversation", agent: "Agent" };
// The agent reports what it really did: [{tool, summary, ok, ms}] -> the same [title, detail] pairs the fixed routes use.
export const TOOL_TITLES = {
  search_products: "Searched products", get_product: "Checked a product", search_policies: "Read store policies",
  view_cart: "Looked at your cart", add_to_cart: "Updated your cart", remove_from_cart: "Updated your cart", start_checkout: "Started checkout",
};
export const stepsFor = (route, steps) => (steps?.length
  ? steps.map((s) => [s.ok === false ? `${TOOL_TITLES[s.tool] || s.tool} (failed)` : TOOL_TITLES[s.tool] || s.tool, s.summary])
  : AGENT_STEPS[route]);
export const routeLabel = (route) => LABELS[route] || "Conversation";
