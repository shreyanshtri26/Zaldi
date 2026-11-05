import ChatPage from "./features/chat/ChatPage.jsx";
import AdminPage from "./features/admin/AdminPage.jsx";

// Two routes, so plain pathname beats pulling in a router. Each page renders its own shell.
export default function App() {
  return window.location.pathname.startsWith("/admin") ? <AdminPage /> : <ChatPage />;
}
