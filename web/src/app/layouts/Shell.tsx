import { LogOut, Menu, X } from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../../hooks/useAuth";

const NAV = [
  ["/overview", "Overview"], ["/products", "Products"], ["/knowledge", "Knowledge"],
  ["/agents", "Agents"], ["/chats", "Chats"], ["/cms", "CMS"],
] as const;

const pill = ({ isActive }: { isActive: boolean }) =>
  `rounded-full border px-3.5 py-1.5 text-[13px] font-medium transition ${isActive
    ? "border-primary bg-primary text-app"
    : "border-line bg-surface text-ink2 hover:text-ink"}`;

export default function Shell() {
  const [open, setOpen] = useState(false);
  const { logout } = useAuth();
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-30 border-b border-line bg-app/95 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-[1500px] items-center gap-3 px-4 sm:px-8">
          <a href="/agents" className="flex items-center gap-2 font-bold">
            <img src="/zaldi_mark.svg" alt="" className="h-7 w-7 rounded-lg bg-white p-1" />Zaldi
          </a>
          <nav className="ml-4 hidden gap-1.5 md:flex" aria-label="Main">
            {NAV.map(([to, label]) => <NavLink key={to} to={to} className={pill}>{label}</NavLink>)}
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <button onClick={logout} className="hidden items-center gap-1.5 rounded-lg px-2 py-1.5 text-ink2 hover:text-ink sm:flex" aria-label="Log out">
              <LogOut size={15} />Log out
            </button>
            <button className="rounded-lg border border-line p-2 md:hidden" aria-label={open ? "Close menu" : "Open menu"} aria-expanded={open} onClick={() => setOpen(!open)}>
              {open ? <X size={18} /> : <Menu size={18} />}
            </button>
          </div>
        </div>
        {open && (
          <nav className="grid gap-1.5 border-t border-line px-4 py-3 md:hidden" aria-label="Main">
            {NAV.map(([to, label]) => <NavLink key={to} to={to} className={pill} onClick={() => setOpen(false)}>{label}</NavLink>)}
            <button onClick={logout} className="rounded-full border border-line px-3.5 py-1.5 text-left text-ink2">Log out</button>
          </nav>
        )}
      </header>
      <main className="mx-auto max-w-[1500px] px-4 py-6 sm:px-8 sm:py-8"><Outlet /></main>
    </div>
  );
}
