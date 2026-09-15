"use client";

import { useEffect, useRef, useState } from "react";

/**
 * The hero's one WebGL moment: a square of vermilion paper, printed with a real
 * sentence from the demo data, folding along its creases and settling into the
 * folded form the product is named for.
 *
 * It is decoration. Nothing in the product depends on it, and it never runs on a
 * phone, under `prefers-reduced-motion`, on a data-saving connection, on a small
 * device, or without WebGL. Three.js is imported only when the scene will render.
 * A static crease pattern of the same five folds is the fallback everywhere else.
 */
export function FoldScene({ className }: { className?: string }) {
  const host = useRef<HTMLDivElement>(null);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    const node = host.current;
    if (!node) return;
    const wideEnough = window.matchMedia("(min-width: 1024px)").matches;
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const connection = (navigator as { connection?: { saveData?: boolean } }).connection;
    const memory = (navigator as { deviceMemory?: number }).deviceMemory;
    if (!wideEnough || reducedMotion || connection?.saveData || (memory !== undefined && memory < 4)) return;

    let disposed = false;
    let stop = () => {};

    void (async () => {
      const THREE = await import("three");
      if (disposed) return;

      let renderer: InstanceType<typeof THREE.WebGLRenderer>;
      try {
        renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "low-power" });
      } catch {
        return; // no WebGL: the static crease pattern stays
      }

      const width = node.clientWidth;
      const height = node.clientHeight;
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.75));
      renderer.setSize(width, height);
      renderer.setClearAlpha(0);
      node.appendChild(renderer.domElement);
      renderer.domElement.setAttribute("aria-hidden", "true");

      const scene = new THREE.Scene();
      const camera = new THREE.PerspectiveCamera(34, width / height, 0.1, 100);
      camera.position.set(0, 0, 6.1);
      scene.add(new THREE.HemisphereLight(0xffffff, 0xd8cfbe, 1.35));
      const key = new THREE.DirectionalLight(0xffffff, 1.5);
      key.position.set(-2.5, 3.5, 4);
      scene.add(key);

      // The sheet carries the demo patient's own sentence and a line from their report.
      const texture = new THREE.CanvasTexture(printedSheet());
      texture.anisotropy = Math.min(4, renderer.capabilities.getMaxAnisotropy());

      const SIZE = 3.4;
      const geometry = new THREE.PlaneGeometry(SIZE, SIZE, 14, 14);
      const flat = Float32Array.from(geometry.attributes.position!.array);
      const sheet = new THREE.Mesh(
        geometry,
        new THREE.MeshStandardMaterial({ map: texture, side: THREE.DoubleSide, roughness: 0.94, metalness: 0 }),
      );
      const group = new THREE.Group();
      group.add(sheet);
      group.rotation.set(-0.35, 0.5, 0.12);
      scene.add(group);

      // Three rigid folds, each rotating everything on one side of a crease.
      const creases = [
        { axis: new THREE.Vector3(0, 1, 0), test: (p: InstanceType<typeof THREE.Vector3>) => p.x > 0.001, angle: -Math.PI * 0.98 },
        { axis: new THREE.Vector3(1, 0, 0), test: (p: InstanceType<typeof THREE.Vector3>) => p.y > 0.001, angle: Math.PI * 0.94 },
        {
          axis: new THREE.Vector3(1, 1, 0).normalize(),
          test: (p: InstanceType<typeof THREE.Vector3>) => p.x - p.y > 0.001,
          angle: -Math.PI * 0.7,
        },
      ];

      const origin = new THREE.Vector3(0, 0, 0);
      const point = new THREE.Vector3();
      const position = geometry.attributes.position!;

      const easeOut = (x: number) => 1 - Math.pow(1 - x, 3);
      const clamp01 = (x: number) => Math.min(1, Math.max(0, x));

      function foldTo(progress: number) {
        for (let i = 0; i < position.count; i++) {
          point.set(flat[i * 3]!, flat[i * 3 + 1]!, flat[i * 3 + 2]!);
          creases.forEach((crease, index) => {
            const local = easeOut(clamp01(progress * creases.length - index));
            if (local <= 0) return;
            if (!crease.test(point)) return;
            point.sub(origin).applyAxisAngle(crease.axis, crease.angle * local).add(origin);
          });
          position.setXYZ(i, point.x, point.y, point.z);
        }
        position.needsUpdate = true;
        geometry.computeVertexNormals();
      }

      const pointer = { x: 0, y: 0 };
      const onPointerMove = (event: PointerEvent) => {
        const rect = node.getBoundingClientRect();
        pointer.x = ((event.clientX - rect.left) / rect.width - 0.5) * 2;
        pointer.y = ((event.clientY - rect.top) / rect.height - 0.5) * 2;
      };
      window.addEventListener("pointermove", onPointerMove, { passive: true });

      let visible = true;
      const observer = new IntersectionObserver(([entry]) => (visible = entry?.isIntersecting ?? true), { threshold: 0.05 });
      observer.observe(node);

      const clock = new THREE.Clock();
      let frame = 0;
      const DELAY = 0.35;
      const DURATION = 3.4;
      const render = () => {
        frame = requestAnimationFrame(render);
        if (!visible) return;
        const time = clock.getElapsedTime();
        foldTo(clamp01((time - DELAY) / DURATION));
        group.rotation.y += ((0.5 + pointer.x * 0.35) - group.rotation.y) * 0.03;
        group.rotation.x += ((-0.35 + pointer.y * 0.2) - group.rotation.x) * 0.03;
        group.position.y = Math.sin(time * 0.5) * 0.05;
        renderer.render(scene, camera);
      };
      frame = requestAnimationFrame(render);
      setRunning(true);

      const onResize = () => {
        const w = node.clientWidth;
        const h = node.clientHeight;
        camera.aspect = w / h;
        camera.updateProjectionMatrix();
        renderer.setSize(w, h);
      };
      window.addEventListener("resize", onResize);

      stop = () => {
        cancelAnimationFrame(frame);
        observer.disconnect();
        window.removeEventListener("resize", onResize);
        window.removeEventListener("pointermove", onPointerMove);
        geometry.dispose();
        texture.dispose();
        (sheet.material as { dispose: () => void }).dispose();
        renderer.dispose();
        renderer.domElement.remove();
      };
    })();

    return () => {
      disposed = true;
      stop();
    };
  }, []);

  return (
    <div ref={host} className={className} aria-hidden>
      {running ? null : <CreasePattern />}
    </div>
  );
}

/** The sheet's printed face: the patient's words and one line of their report. */
function printedSheet(): HTMLCanvasElement {
  const canvas = document.createElement("canvas");
  canvas.width = 512;
  canvas.height = 512;
  const ctx = canvas.getContext("2d")!;
  ctx.fillStyle = "#d83a2e";
  ctx.fillRect(0, 0, 512, 512);

  // Kozo fibre, drawn rather than shipped as an image.
  ctx.strokeStyle = "rgba(255,255,255,0.09)";
  ctx.lineWidth = 1;
  for (let i = 0; i < 160; i++) {
    const x = Math.random() * 512;
    const y = Math.random() * 512;
    const length = 8 + Math.random() * 26;
    const angle = Math.random() * Math.PI;
    ctx.beginPath();
    ctx.moveTo(x, y);
    ctx.lineTo(x + Math.cos(angle) * length, y + Math.sin(angle) * length);
    ctx.stroke();
  }

  // The app's own font stack, so the sheet is printed in the product's type.
  const family = getComputedStyle(document.body).fontFamily || "sans-serif";
  ctx.fillStyle = "rgba(255,255,255,0.94)";
  ctx.font = `400 25px ${family}`;
  ctx.fillText("கடந்த மூன்று நாட்களாக", 48, 150);
  ctx.fillText("தலைவலி மற்றும் தலைச்சுற்றல்.", 48, 190);
  ctx.fillStyle = "rgba(255,255,255,0.7)";
  ctx.font = `400 19px ${family}`;
  ctx.fillText("Hemoglobin: 13.5 g/dL", 48, 268);
  ctx.fillText("Blood pressure: 150/95 mmHg", 48, 300);
  return canvas;
}

/** The same five folds, drawn flat: the fallback, and what a print or a screen reader gets. */
function CreasePattern() {
  return (
    <svg viewBox="0 0 320 320" className="size-full" role="presentation">
      <rect x="20" y="20" width="280" height="280" rx="2" fill="#d83a2e" />
      <g stroke="#ffffff" fill="none" strokeLinecap="round">
        <path d="M20 20 L300 300" opacity=".55" />
        <path d="M300 20 L20 300" opacity=".55" />
        <path d="M160 20 L160 300" opacity=".4" strokeDasharray="9 8" />
        <path d="M20 160 L300 160" opacity=".4" strokeDasharray="9 8" />
        <path d="M90 20 L90 300" opacity=".25" strokeDasharray="5 9" />
        <path d="M230 20 L230 300" opacity=".25" strokeDasharray="5 9" />
      </g>
    </svg>
  );
}
