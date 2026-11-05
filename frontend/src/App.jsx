import ChatPage from "./features/chat/ChatPage.jsx";
import AdminPage from "./features/admin/AdminPage.jsx";

// Two routes, so plain pathname beats pulling in a router. Everything ships in one cached bundle: no per-view loading.
export default function App() {
  return window.location.pathname.startsWith("/admin") ? <AdminPage /> : <ChatPage />;
}
