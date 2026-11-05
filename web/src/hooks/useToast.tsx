import { createContext, useCallback, useContext, useState, type ReactNode } from "react";

type Tone = "ok" | "bad";
interface Toast { id: number; text: string; tone: Tone }
const Ctx = createContext<(text: string, tone?: Tone) => void>(() => {});
export const useToast = () => useContext(Ctx);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const push = useCallback((text: string, tone: Tone = "ok") => {
    const id = Date.now() + Math.random();
    setItems((t) => [...t, { id, text, tone }]);
    setTimeout(() => setItems((t) => t.filter((x) => x.id !== id)), 3500);
  }, []);
  return (
    <Ctx.Provider value={push}>
      {children}
      <div className="pointer-events-none fixed inset-x-4 bottom-4 z-50 flex flex-col items-end gap-2" role="status" aria-live="polite">
        {items.map((t) => (
          <div key={t.id} className={`pointer-events-auto max-w-sm rounded-lg border px-4 py-2.5 shadow-lg ${t.tone === "ok" ? "border-ok/40 bg-surface text-ink" : "border-bad/40 bg-surface text-bad"}`}>
            {t.text}
          </div>
        ))}
      </div>
    </Ctx.Provider>
  );
}
