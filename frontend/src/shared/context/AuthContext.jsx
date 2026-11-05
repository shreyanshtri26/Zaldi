import { createContext, useContext, useState } from "react";
import { login as apiLogin } from "../../api/client.js";

const AuthContext = createContext(null);
export const useAuth = () => useContext(AuthContext);

// Token lives in sessionStorage: survives reload, cleared when the tab closes.
const read = () => { try { return sessionStorage.getItem("zaldi_admin") || ""; } catch { return ""; } };

export function AuthProvider({ children }) {
  const [token, setToken] = useState(read);

  async function login(candidate) {
    await apiLogin(candidate); // throws on a wrong token
    try { sessionStorage.setItem("zaldi_admin", candidate); } catch {}
    setToken(candidate);
  }
  function logout() {
    try { sessionStorage.removeItem("zaldi_admin"); } catch {}
    setToken("");
  }
  return <AuthContext.Provider value={{ token, login, logout }}>{children}</AuthContext.Provider>;
}
