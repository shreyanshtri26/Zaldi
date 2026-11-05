import { useCallback, useEffect, useState } from "react";

// Chat history lives in this browser only (the API is stateless), so a failed read/write must never break the UI.
const KEY = "zaldi_chats_v1";
const load = () => { try { return JSON.parse(localStorage.getItem(KEY)) || []; } catch { return []; } };

export default function useChats() {
  const [chats, setChats] = useState(load);
  const [activeId, setActiveId] = useState(null); // null = fresh "new chat" screen

  useEffect(() => { try { localStorage.setItem(KEY, JSON.stringify(chats.slice(0, 50))); } catch {} }, [chats]);

  const active = chats.find((c) => c.id === activeId) || null;

  // Appends messages to the active chat, creating it (titled from the first user message) if needed. Returns the chat id.
  const append = useCallback((id, ...messages) => {
    const cid = id || String(Date.now());
    setActiveId(cid);
    setChats((all) => {
      const existing = all.find((c) => c.id === cid);
      if (!existing) {
        const first = messages.find((m) => m.role === "user")?.text || "New chat";
        return [{ id: cid, title: first.slice(0, 48), updatedAt: Date.now(), messages }, ...all];
      }
      return [{ ...existing, updatedAt: Date.now(), messages: [...existing.messages, ...messages] }, ...all.filter((c) => c.id !== cid)];
    });
    return cid;
  }, []);

  const remove = (id) => {
    setChats((all) => all.filter((c) => c.id !== id));
    if (id === activeId) setActiveId(null);
  };

  return { chats, active, activeId, select: setActiveId, newChat: () => setActiveId(null), append, remove };
}
