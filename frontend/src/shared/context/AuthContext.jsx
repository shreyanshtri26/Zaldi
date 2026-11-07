import { createContext, useContext, useState } from "react";
import { accountLogin, accountLoginTwoStep, login as apiLogin, setStore, signupStore } from "../../api/client.js";

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
  async function signedIn(account) {
    setStore(account.store === "default" ? "" : account.store); // the owner works in their own store
    await login(account.token);
  }
  // Returns null when signed in, or { challenge } when the account needs its two-step code next.
  async function loginAccount(email, password) {
    const res = await accountLogin(email, password);
    if (res.needs_two_step) return { challenge: res.challenge };
    await signedIn(res);
    return null;
  }
  async function finishTwoStep(challenge, code) { await signedIn(await accountLoginTwoStep(challenge, code)); }
  async function signup(body) {
    const made = await signupStore(body);
    setStore(made.store.slug);
    await login(made.token);
  }
  function logout() {
    try { sessionStorage.removeItem("zaldi_admin"); } catch {}
    setToken("");
  }
  return <AuthContext.Provider value={{ token, login, loginAccount, finishTwoStep, signup, logout }}>{children}</AuthContext.Provider>;
}
