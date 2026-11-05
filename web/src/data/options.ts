import { BookOpen, Boxes, Bot, Package, PenLine, ShoppingBag, type LucideIcon } from "lucide-react";
import type { AgentStatus } from "../types";

export interface Option { id: string; label: string; hint: string }

export const CAPABILITIES: Option[] = [
  { id: "product_search", label: "Product search", hint: "Find products by price, colour, size and category" },
  { id: "product_comparison", label: "Product comparison", hint: "Compare products side by side" },
  { id: "policy_lookup", label: "Policy lookup", hint: "Answer from shipping, returns and payment policies" },
  { id: "knowledge_retrieval", label: "Knowledge retrieval", hint: "Search connected knowledge sources" },
  { id: "order_lookup", label: "Order lookup", hint: "Look up order status" },
  { id: "inventory_lookup", label: "Inventory lookup", hint: "Check stock levels" },
  { id: "content_generation", label: "Content generation", hint: "Draft descriptions and storefront copy" },
];

export const TOOLS: Option[] = [
  { id: "catalogue_search", label: "Catalogue search", hint: "Hybrid semantic + keyword product search" },
  { id: "inventory_api", label: "Inventory API", hint: "Live stock quantities" },
  { id: "order_api", label: "Order API", hint: "Order status and history" },
  { id: "cms_api", label: "CMS API", hint: "Read and propose content changes" },
  { id: "search", label: "Policy search", hint: "Vector search over store policies" },
];

export const PERMISSIONS: Option[] = [
  { id: "read_products", label: "Read products", hint: "View catalogue data" },
  { id: "update_products", label: "Update product data", hint: "Change prices, stock or descriptions" },
  { id: "read_policies", label: "Read policies", hint: "View store policies" },
  { id: "edit_policies", label: "Edit policies", hint: "Propose policy changes" },
  { id: "publish_content", label: "Publish content", hint: "Make content live" },
  { id: "read_orders", label: "Access order information", hint: "View customer orders" },
];

export const APPROVAL_ACTIONS: Option[] = [
  { id: "edit_policies", label: "Editing a policy", hint: "A merchant must approve every policy change" },
  { id: "update_products", label: "Changing product data", hint: "Price, stock or description edits" },
  { id: "publish_content", label: "Publishing content", hint: "Anything that goes live to customers" },
  { id: "read_orders", label: "Opening order details", hint: "Sensitive customer information" },
];

export const LANGUAGES = ["English", "Hindi", "Hinglish"];

export const ICONS: Record<string, LucideIcon> = {
  bot: Bot, "shopping-bag": ShoppingBag, package: Package, book: BookOpen, pen: PenLine, boxes: Boxes,
};

export const STATUS_TONE: Record<AgentStatus, "ok" | "warn" | "mute"> = { active: "ok", paused: "warn", draft: "mute" };

export const labelOf = (list: Option[], id: string) => list.find((o) => o.id === id)?.label ?? id;
