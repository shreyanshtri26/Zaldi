import { useAuth } from "../../shared/context/AuthContext.jsx";
import { ToastProvider } from "../../shared/context/ToastContext.jsx";
import AdminWorkspace from "./AdminWorkspace.jsx";
import LoginForm from "./LoginForm.jsx";

// Shows the login form until an admin token has been verified.
export default function AdminPage() {
  const { token } = useAuth();
  return <ToastProvider>{token ? <AdminWorkspace /> : <LoginForm />}</ToastProvider>;
}
