import { useEffect, useRef } from "react";
import Lenis from "lenis";
import "lenis/dist/lenis.css";

// Smooth inertial scrolling for one scroll container. `ref` must be the scroll wrapper whose
// first child is the (stable) content element. Returns a ref holding the Lenis instance (null when reduced-motion).
export default function useLenis(ref) {
  const lenis = useRef(null);
  useEffect(() => {
    const wrapper = ref.current;
    if (!wrapper || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const l = new Lenis({ wrapper, content: wrapper.firstElementChild, lerp: 0.09, wheelMultiplier: 0.9 });
    lenis.current = l;
    let raf = requestAnimationFrame(function tick(t) { l.raf(t); raf = requestAnimationFrame(tick); });
    return () => { cancelAnimationFrame(raf); l.destroy(); lenis.current = null; };
  }, [ref]);
  return lenis;
}
