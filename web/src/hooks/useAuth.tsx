import { createContext, useContext, useState, type ReactNode } from "react";
import { api, tokenStore } from "../services/api";

interface Auth { authed: boolean; login: (t: string) => Promise<void>; logout: () => void }
const Ctx = createContext<Auth>({ authed: false, login: async () => {}, logout: () => {} });
export const useAuth = () => useContext(Ctx);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [authed, setAuthed] = useState(() => !!tokenStore.get());
  const login = async (token: string) => { await api.login(token); tokenStore.set(token); setAuthed(true); };
  const logout = () => { tokenStore.clear(); setAuthed(false); };
  return <Ctx.Provider value={{ authed, login, logout }}>{children}</Ctx.Provider>;
}
