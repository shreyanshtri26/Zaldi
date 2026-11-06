import { createContext, useContext, useState } from "react";
import { accountLogin, login as apiLogin, setStore, signupStore } from "../../api/client.js";

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
  async function loginAccount(email, password) {
    const account = await accountLogin(email, password);
    setStore(account.store === "default" ? "" : account.store); // the owner works in their own store
    await login(account.token);
  }
  async function signup(body) {
    const made = await signupStore(body);
    setStore(made.store.slug);
    await login(made.token);
  }
  function logout() {
    try { sessionStorage.removeItem("zaldi_admin"); } catch {}
    setToken("");
  }
  return <AuthContext.Provider value={{ token, login, loginAccount, signup, logout }}>{children}</AuthContext.Provider>;
}
