import { Navigate, Route, Routes } from "react-router-dom";
import AgentDetail from "../features/agents/AgentDetail";
import AgentWizard from "../features/agents/AgentWizard";
import AgentsPage from "../features/agents/AgentsPage";
import Login from "../features/auth/Login";
import ComingSoon from "../features/ComingSoon";
import { useAuth } from "../hooks/useAuth";
import Shell from "./layouts/Shell";

export default function App() {
  const { authed } = useAuth();
  if (!authed) return <Login />;
  return (
    <Routes>
      <Route element={<Shell />}>
        <Route index element={<Navigate to="/agents" replace />} />
        <Route path="agents" element={<AgentsPage />} />
        <Route path="agents/new" element={<AgentWizard />} />
        <Route path="agents/:id" element={<AgentDetail />} />
        <Route path="overview" element={<ComingSoon title="Overview" phase="Phase 1" />} />
        <Route path="products" element={<ComingSoon title="Products" phase="Phase 1" />} />
        <Route path="knowledge" element={<ComingSoon title="Knowledge" phase="Phase 1" />} />
        <Route path="chats" element={<ComingSoon title="Chats" phase="Phase 1" />} />
        <Route path="cms" element={<ComingSoon title="CMS" phase="Phase 3" />} />
        <Route path="*" element={<Navigate to="/agents" replace />} />
      </Route>
    </Routes>
  );
}
