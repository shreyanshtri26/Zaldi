import { useEffect, useState } from "react";
import { getCategories } from "../../api/client.js";

// Categories of the connected store for the home page. Failure just means no category row.
export default function useCategories() {
  const [data, setData] = useState({ categories: [], shown: 6 });
  useEffect(() => {
    let live = true;
    getCategories().then((d) => live && setData(d)).catch(() => {});
    return () => { live = false; };
  }, []);
  return data;
}
