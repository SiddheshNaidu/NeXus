"use client";

import React, { useEffect, useRef } from "react";

// Tiered performance config based on device class
function getDeviceConfig(width: number) {
  if (width < 640) return null; // phones: off
  if (width < 1024) {
    return { particleDivisor: 28000, speedMultiplier: 0.5, connectionDistDivisor: 10, mouseRadius: 120, particleOpacity: 0.7 };
  }
  return { particleDivisor: 14000, speedMultiplier: 1, connectionDistDivisor: 7, mouseRadius: 200, particleOpacity: 1 };
}

export const AetherFlowBackground = () => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const isVisibleRef = useRef(true);
  const rafRef = useRef<number>(0);

  useEffect(() => {
    const config = getDeviceConfig(window.innerWidth);
    if (!config) return;

    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // --- Intersection Observer: pause RAF when off-screen ---
    const observer = new IntersectionObserver(
      ([entry]) => { isVisibleRef.current = entry.isIntersecting; },
      { threshold: 0.05 }
    );
    observer.observe(canvas);

    const mouse = { x: null as number | null, y: null as number | null, radius: config.mouseRadius };

    class Particle {
      x: number; y: number;
      dX: number; dY: number;
      size: number; color: string;
      constructor(x: number, y: number, dX: number, dY: number, size: number, color: string) {
        this.x = x; this.y = y; this.dX = dX; this.dY = dY; this.size = size; this.color = color;
      }
      draw() {
        ctx!.beginPath();
        ctx!.arc(this.x, this.y, this.size, 0, Math.PI * 2, false);
        ctx!.fillStyle = this.color;
        ctx!.fill();
      }
      update() {
        if (this.x > canvas!.width || this.x < 0) this.dX = -this.dX;
        if (this.y > canvas!.height || this.y < 0) this.dY = -this.dY;
        if (mouse.x !== null && mouse.y !== null) {
          const dx = mouse.x - this.x, dy = mouse.y - this.y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < mouse.radius + this.size) {
            const fx = dx / dist, fy = dy / dist;
            const force = (mouse.radius - dist) / mouse.radius;
            this.x -= fx * force * 5;
            this.y -= fy * force * 5;
          }
        }
        this.x += this.dX;
        this.y += this.dY;
        this.draw();
      }
    }

    let particles: Particle[] = [];

    function init() {
      particles = [];
      const w = canvas!.width, h = canvas!.height;
      const count = Math.round((w * h) / config!.particleDivisor);
      for (let i = 0; i < count; i++) {
        const size = Math.random() * 2 + 1;
        const x = Math.random() * (w - size * 4) + size * 2;
        const y = Math.random() * (h - size * 4) + size * 2;
        const dX = ((Math.random() * 0.4) - 0.2) * config!.speedMultiplier;
        const dY = ((Math.random() * 0.4) - 0.2) * config!.speedMultiplier;
        particles.push(new Particle(x, y, dX, dY, size, `rgba(129,140,248,${config!.particleOpacity})`));
      }
    }

    function connect() {
      const threshold =
        (canvas!.width / config!.connectionDistDivisor) *
        (canvas!.height / config!.connectionDistDivisor);
      for (let a = 0; a < particles.length; a++) {
        for (let b = a; b < particles.length; b++) {
          const dist =
            (particles[a].x - particles[b].x) ** 2 +
            (particles[a].y - particles[b].y) ** 2;
          if (dist < threshold) {
            const opacity = 1 - dist / 20000;
            const dxm = particles[a].x - (mouse.x ?? 0);
            const dym = particles[a].y - (mouse.y ?? 0);
            const distm = Math.sqrt(dxm * dxm + dym * dym);
            ctx!.strokeStyle =
              mouse.x !== null && distm < mouse.radius
                ? `rgba(255,255,255,${opacity})`
                : `rgba(99,102,241,${opacity})`;
            ctx!.lineWidth = 1.5;
            ctx!.beginPath();
            ctx!.moveTo(particles[a].x, particles[a].y);
            ctx!.lineTo(particles[b].x, particles[b].y);
            ctx!.stroke();
          }
        }
      }
    }

    function animate() {
      rafRef.current = requestAnimationFrame(animate);
      // Skip draw when off-screen — saves GPU entirely
      if (!isVisibleRef.current) return;
      ctx!.clearRect(0, 0, canvas!.width, canvas!.height);
      particles.forEach(p => p.update());
      connect();
    }

    // Size canvas to its parent container, not the viewport
    const resizeCanvas = () => {
      const parent = canvas!.parentElement;
      if (!parent) return;
      canvas!.width = parent.offsetWidth;
      canvas!.height = parent.offsetHeight;
      init();
    };

    const onMouseMove = (e: MouseEvent) => {
      const rect = canvas!.getBoundingClientRect();
      mouse.x = e.clientX - rect.left;
      mouse.y = e.clientY - rect.top;
    };
    const onMouseOut = () => { mouse.x = null; mouse.y = null; };

    const ro = new ResizeObserver(resizeCanvas);
    if (canvas.parentElement) ro.observe(canvas.parentElement);

    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseout", onMouseOut);

    resizeCanvas();
    animate();

    return () => {
      observer.disconnect();
      ro.disconnect();
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseout", onMouseOut);
      cancelAnimationFrame(rafRef.current);
    };
  }, []);

  // Don't mount canvas at all on phones
  if (typeof window !== "undefined" && window.innerWidth < 640) return null;

  return (
    <canvas
      ref={canvasRef}
      className="absolute inset-0 w-full h-full pointer-events-none z-0"
    />
  );
};