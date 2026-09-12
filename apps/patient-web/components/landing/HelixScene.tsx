"use client";

import { useEffect, useRef, useState } from "react";

/**
 * The hero's one WebGL scene: scattered information drawing itself into the rod
 * of Asclepius. It is decoration — nothing in the product depends on it.
 *
 * It never runs on a phone, never runs under `prefers-reduced-motion`, never runs
 * without WebGL, and pauses whenever it scrolls out of view. Three.js is imported
 * dynamically so the bundle is only fetched when the scene will actually render.
 */
export function HelixScene({ className }: { className?: string }) {
  const host = useRef<HTMLDivElement>(null);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    const node = host.current;
    if (!node) return;
    const wideEnough = window.matchMedia("(min-width: 1024px)").matches;
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (!wideEnough || reducedMotion) return;

    let disposed = false;
    let stop = () => {};

    void (async () => {
      const THREE = await import("three");
      const { gsap } = await import("gsap");
      if (disposed) return;

      let renderer: InstanceType<typeof THREE.WebGLRenderer>;
      try {
        renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "low-power" });
      } catch {
        return; // no WebGL: the static fallback stays
      }

      const width = node.clientWidth;
      const height = node.clientHeight;
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.75));
      renderer.setSize(width, height);
      renderer.setClearAlpha(0);
      node.appendChild(renderer.domElement);
      renderer.domElement.setAttribute("aria-hidden", "true");

      const scene = new THREE.Scene();
      scene.fog = new THREE.Fog(0xf5f8f7, 7, 16);
      const camera = new THREE.PerspectiveCamera(38, width / height, 0.1, 100);
      camera.position.set(0, 0, 8.4);

      const group = new THREE.Group();
      scene.add(group);

      // The rod itself.
      const rod = new THREE.Mesh(
        new THREE.CylinderGeometry(0.022, 0.022, 6.6, 8),
        new THREE.MeshBasicMaterial({ color: 0x0a5c52, transparent: true, opacity: 0.55 }),
      );
      group.add(rod);

      // Information: scattered at first, then ordered along the rod.
      const COUNT = 132;
      const jade = new THREE.Color(0x0a5c52);
      const steel = new THREE.Color(0x47606e);
      const nodes = new THREE.InstancedMesh(
        new THREE.IcosahedronGeometry(0.062, 1),
        new THREE.MeshBasicMaterial({ transparent: true, opacity: 0.92 }),
        COUNT,
      );
      const scattered: InstanceType<typeof THREE.Vector3>[] = [];
      const ordered: InstanceType<typeof THREE.Vector3>[] = [];
      const spin: number[] = [];
      for (let i = 0; i < COUNT; i++) {
        const p = i / (COUNT - 1);
        const angle = p * Math.PI * 6 + (i % 2 === 0 ? 0 : Math.PI);
        ordered.push(new THREE.Vector3(Math.cos(angle) * 1.28, (p - 0.5) * 6.1, Math.sin(angle) * 1.28));
        scattered.push(
          new THREE.Vector3((Math.random() - 0.5) * 9, (Math.random() - 0.5) * 7, (Math.random() - 0.5) * 5 - 0.6),
        );
        spin.push(Math.random() * Math.PI);
        // A third of the items are the patient's confirmed ones.
        nodes.setColorAt(i, i % 3 === 0 ? jade : steel);
      }
      nodes.instanceColor!.needsUpdate = true;
      group.add(nodes);

      const dummy = new THREE.Object3D();
      const progress = { value: 0 };
      const pointer = { x: 0, y: 0 };

      const onPointerMove = (event: PointerEvent) => {
        const rect = node.getBoundingClientRect();
        pointer.x = ((event.clientX - rect.left) / rect.width - 0.5) * 2;
        pointer.y = ((event.clientY - rect.top) / rect.height - 0.5) * 2;
      };
      window.addEventListener("pointermove", onPointerMove, { passive: true });

      // Assembly: the one piece of storytelling motion here.
      const intro = gsap.to(progress, { value: 1, duration: 2.2, ease: "power3.inOut", delay: 0.15 });

      let frame = 0;
      let visible = true;
      const observer = new IntersectionObserver(([entry]) => (visible = entry?.isIntersecting ?? true), {
        threshold: 0.05,
      });
      observer.observe(node);

      const clock = new THREE.Clock();
      const render = () => {
        frame = requestAnimationFrame(render);
        if (!visible) return;
        const time = clock.getElapsedTime();
        const eased = progress.value;
        for (let i = 0; i < COUNT; i++) {
          const from = scattered[i]!;
          const to = ordered[i]!;
          const drift = Math.sin(time * 0.6 + spin[i]!) * 0.045 * eased;
          dummy.position.set(
            from.x + (to.x - from.x) * eased,
            from.y + (to.y - from.y) * eased + drift,
            from.z + (to.z - from.z) * eased,
          );
          const scale = 0.55 + eased * 0.45;
          dummy.scale.setScalar(scale);
          dummy.rotation.set(time * 0.25 + spin[i]!, time * 0.2, 0);
          dummy.updateMatrix();
          nodes.setMatrixAt(i, dummy.matrix);
        }
        nodes.instanceMatrix.needsUpdate = true;
        rod.scale.y = eased;
        group.rotation.y += 0.0016;
        group.rotation.x += (pointer.y * 0.12 - group.rotation.x) * 0.04;
        group.position.x += (pointer.x * 0.22 - group.position.x) * 0.04;
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
        intro.kill();
        observer.disconnect();
        window.removeEventListener("resize", onResize);
        window.removeEventListener("pointermove", onPointerMove);
        nodes.geometry.dispose();
        (nodes.material as { dispose: () => void }).dispose();
        rod.geometry.dispose();
        (rod.material as { dispose: () => void }).dispose();
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
      {/* Fallback: the same idea, drawn flat, for phones, reduced motion and no WebGL. */}
      {running ? null : (
        <svg viewBox="0 0 320 380" className="size-full" role="presentation">
          <defs>
            <linearGradient id="asc-rod" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#0a5c52" stopOpacity="0.15" />
              <stop offset="45%" stopColor="#0a5c52" stopOpacity="0.75" />
              <stop offset="100%" stopColor="#0a5c52" stopOpacity="0.15" />
            </linearGradient>
          </defs>
          <line x1="160" y1="26" x2="160" y2="354" stroke="url(#asc-rod)" strokeWidth="3" strokeLinecap="round" />
          {Array.from({ length: 26 }, (_, i) => {
            const p = i / 25;
            const angle = p * Math.PI * 5;
            return (
              <circle
                key={i}
                cx={160 + Math.cos(angle) * 74}
                cy={34 + p * 312}
                r={i % 3 === 0 ? 5.5 : 4}
                fill={i % 3 === 0 ? "#0a5c52" : "#47606e"}
                opacity={i % 3 === 0 ? 0.85 : 0.45}
              />
            );
          })}
        </svg>
      )}
    </div>
  );
}
