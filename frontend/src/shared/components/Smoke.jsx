import { useEffect, useRef, useState } from "react";

// Soft vapour drifting out from behind the orb. One fullscreen-triangle fragment shader (layered noise), capped at ~30fps,
// paused when hidden or off screen. No WebGL or reduced motion -> three static CSS blobs instead.
const VERT = "attribute vec2 p;void main(){gl_Position=vec4(p,0.,1.);}";
const FRAG = `precision mediump float;
uniform vec2 r;uniform float t;uniform float g;uniform vec3 c1;uniform vec3 c2;
float h(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
float n(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);
  return mix(mix(h(i),h(i+vec2(1,0)),f.x),mix(h(i+vec2(0,1)),h(i+vec2(1,1)),f.x),f.y);}
float fbm(vec2 p){float a=.5,s=0.;for(int i=0;i<4;i++){s+=a*n(p);p=p*2.02+vec2(1.7,9.2);a*=.5;}return s;}
void main(){
  vec2 uv=(gl_FragCoord.xy/r-.5)*2.;float d=length(uv);
  vec2 q=uv*1.7+vec2(t*.05,-t*.09);
  float w=fbm(q+fbm(q*1.3+t*.1));
  float ring=smoothstep(1.,.44,d)*smoothstep(.34,.5,d);
  float a=ring*smoothstep(.3,.62,w)*.95*g;
  gl_FragColor=vec4(mix(c1,c2,w)*a,a);
}`;
const SPEED = { idle: .6, listening: .9, processing: 2.2, responding: 1.2, inactive: 0 };
const GAIN = { idle: .8, listening: 1, processing: 1.15, responding: 1, inactive: 0 };
const rgb = (hex, fallback) => (/^#[0-9a-f]{6}$/i.test(hex) ? [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255) : fallback);

export default function Smoke({ state }) {
  const ref = useRef(null);
  const live = useRef(state);
  const [fallback, setFallback] = useState(false);
  live.current = state;

  useEffect(() => {
    const canvas = ref.current;
    const gl = !matchMedia("(prefers-reduced-motion: reduce)").matches && canvas.getContext("webgl", { antialias: false, premultipliedAlpha: true });
    if (!gl) { setFallback(true); return; }
    const sh = (type, src) => { const s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s); return s; };
    const prog = gl.createProgram();
    gl.attachShader(prog, sh(gl.VERTEX_SHADER, VERT)); gl.attachShader(prog, sh(gl.FRAGMENT_SHADER, FRAG)); gl.linkProgram(prog);
    if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) { setFallback(true); return; }
    gl.useProgram(prog);
    gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
    const loc = gl.getAttribLocation(prog, "p");
    gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
    const u = (name) => gl.getUniformLocation(prog, name);
    const css = getComputedStyle(canvas);
    gl.uniform3fv(u("c1"), rgb(css.getPropertyValue("--c-lime").trim(), [.76, .97, .35]));
    gl.uniform3fv(u("c2"), rgb(css.getPropertyValue("--c-leaf").trim(), [.47, .72, .24]));
    gl.enable(gl.BLEND); gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);

    const size = () => {
      const scale = Math.min(devicePixelRatio || 1, 1.5) * (innerWidth < 600 ? .6 : 1); // lower detail on phones
      canvas.width = Math.round(canvas.clientWidth * scale); canvas.height = Math.round(canvas.clientHeight * scale);
      gl.viewport(0, 0, canvas.width, canvas.height); gl.uniform2f(u("r"), canvas.width, canvas.height);
    };
    size();
    addEventListener("resize", size);

    let visible = true, raf = 0, last = 0, clock = 0, speed = 0, gain = 0;
    const io = new IntersectionObserver(([e]) => { visible = e.isIntersecting; });
    io.observe(canvas);
    const tick = (now) => {
      raf = requestAnimationFrame(tick);
      if (document.hidden || !visible || now - last < 33) return;
      const dt = Math.min((now - last) / 1000, .1); last = now;
      speed += (SPEED[live.current] - speed) * .08; gain += (GAIN[live.current] - gain) * .08; // ease between states
      clock += dt * speed;
      gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT);
      gl.uniform1f(u("t"), clock); gl.uniform1f(u("g"), gain);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
    };
    raf = requestAnimationFrame(tick);
    return () => { cancelAnimationFrame(raf); io.disconnect(); removeEventListener("resize", size); gl.getExtension("WEBGL_lose_context")?.loseContext(); };
  }, []);

  return fallback
    ? <span className="smoke smoke-css" aria-hidden="true"><i /><i /><i /></span>
    : <canvas ref={ref} className="smoke" aria-hidden="true" />;
}
