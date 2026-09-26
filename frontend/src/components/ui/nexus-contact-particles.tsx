"use client";

import React, { useEffect, useRef } from "react";
import { useInView } from "framer-motion";

export function NexusContactParticles() {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const isInView = useInView(containerRef); // Start animation only when in view

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !isInView) return;
    
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    if (!ctx) return;

    let particlesArray: Particle[] = [];
    let animationFrameId: number;

    const resizeCanvas = () => {
      // Set canvas to parent container size
      if (containerRef.current) {
        canvas.width = containerRef.current.clientWidth;
        canvas.height = containerRef.current.clientHeight;
      }
    };
    window.addEventListener("resize", resizeCanvas);
    resizeCanvas();

    const mouse = { x: -1000, y: -1000, radius: 150 };

    const handleMouseMove = (e: MouseEvent) => {
      // Offset mouse coordinates to canvas container
      const rect = canvas.getBoundingClientRect();
      mouse.x = e.clientX - rect.left;
      mouse.y = e.clientY - rect.top;
    };
    const handleMouseLeave = () => {
      mouse.x = -1000;
      mouse.y = -1000;
    };
    
    canvas.addEventListener("mousemove", handleMouseMove);
    canvas.addEventListener("mouseleave", handleMouseLeave);

    // Draw text to get pixel coordinates
    ctx.fillStyle = "white";
    // Scale font size based on screen width
    const fontSize = Math.min(220, canvas.width / 4);
    // User requested "Nevera" font
    ctx.font = `900 ${fontSize}px "Orbitron", "Space Mono", monospace`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText("NEXUS", canvas.width / 2, canvas.height / 2);

    const textCoordinates = ctx.getImageData(0, 0, canvas.width, canvas.height);
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    class Particle {
      x: number;
      y: number;
      size: number;
      baseX: number;
      baseY: number;
      density: number;
      color: string;
      alpha: number;
      speedY: number;
      ascendSpeed: number;

      constructor(x: number, y: number) {
        this.x = Math.random() * canvas!.width;
        // Start randomly way above the screen for rain drop effect
        this.y = (Math.random() * canvas!.height * 2) - (canvas!.height * 2); 
        this.size = Math.random() * 1.5 + 0.5;
        this.baseX = x;
        this.baseY = y;
        this.density = (Math.random() * 30) + 1;
        this.color = Math.random() > 0.8 ? "129, 140, 248" : "255, 255, 255";
        this.alpha = 0;
        this.speedY = Math.random() * 10 + 2; // Fall speed
        this.ascendSpeed = Math.random() * 3 + 1; // Ascend speed
      }

      draw() {
        if (!ctx) return;
        ctx.fillStyle = `rgba(${this.color}, ${this.alpha})`;
        ctx.beginPath();
        ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
        ctx.closePath();
        ctx.fill();
      }

      update(phase: "fall" | "assemble" | "ascend") {
        if (phase === "fall") {
            // Drop like rain
            this.y += this.speedY;
            this.alpha = Math.min(0.8, this.alpha + 0.05);
            
            if (this.y > canvas!.height) {
                this.y = -10;
                this.x = Math.random() * canvas!.width;
            }
        } 
        else if (phase === "assemble") {
            // Instantly snap and form the word
            let dx = this.baseX - this.x;
            let dy = this.baseY - this.y;
            // Snap tightly
            this.x += dx * 0.03;
            this.y += dy * 0.03;
            this.alpha = Math.min(1, this.alpha + 0.02);

            // Hover interactions: repel from cursor
            let mdx = mouse.x - this.x;
            let mdy = mouse.y - this.y;
            let distance = Math.sqrt(mdx * mdx + mdy * mdy);
            if (distance < mouse.radius) {
                const forceDirectionX = mdx / distance;
                const forceDirectionY = mdy / distance;
                const maxDistance = mouse.radius;
                const force = (maxDistance - distance) / maxDistance;
                const directionX = (forceDirectionX * force * this.density);
                const directionY = (forceDirectionY * force * this.density);
                this.x -= directionX;
                this.y -= directionY;
            }
        } 
        else if (phase === "ascend") {
            // Move upwards from the point they started (reverse rain)
            this.y -= this.ascendSpeed;
            this.x += (Math.random() - 0.5) * 2; // Slight drift
            this.alpha = Math.max(0, this.alpha - 0.01);
        }
      }
    }

    function init() {
      particlesArray = [];
      const step = window.innerWidth < 768 ? 8 : 4; 
      for (let y = 0, y2 = textCoordinates.height; y < y2; y += step) {
        for (let x = 0, x2 = textCoordinates.width; x < x2; x += step) {
          if (textCoordinates.data[(y * 4 * textCoordinates.width) + (x * 4) + 3] > 128) {
            particlesArray.push(new Particle(x, y));
          }
        }
      }
    }

    init();

    let currentPhase: "fall" | "assemble" | "ascend" = "fall";
    let phaseTimer: NodeJS.Timeout;

    const cyclePhases = () => {
      // 1. Fall for 3 seconds
      currentPhase = "fall";
      
      // Randomize positions above screen before falling
      particlesArray.forEach(p => {
        p.y = (Math.random() * canvas!.height * 2) - (canvas!.height * 2);
        p.x = Math.random() * canvas!.width;
      });

      phaseTimer = setTimeout(() => {
        // 2. Assemble and hold for 5 seconds
        currentPhase = "assemble";
        
        phaseTimer = setTimeout(() => {
          // 3. Ascend slowly for 3 seconds (to clear the screen)
          currentPhase = "ascend";
          
          phaseTimer = setTimeout(() => {
            // Repeat cycle
            cyclePhases();
          }, 3000);
          
        }, 10000); // Hold for 10s
        
      }, 3000); // Fall for 3s
    };

    cyclePhases();

    function animate() {
      if (!ctx || !canvas) return;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      
      for (let i = 0; i < particlesArray.length; i++) {
        particlesArray[i].draw();
        particlesArray[i].update(currentPhase);
      }
      animationFrameId = requestAnimationFrame(animate);
    }
    
    animate();

    return () => {
      clearTimeout(phaseTimer);
      window.removeEventListener("resize", resizeCanvas);
      canvas.removeEventListener("mousemove", handleMouseMove);
      canvas.removeEventListener("mouseleave", handleMouseLeave);
      cancelAnimationFrame(animationFrameId);
    };
  }, [isInView]);

  return (
    <section 
      ref={containerRef} 
      className="relative w-full h-[80vh] min-h-[600px] flex items-center justify-center overflow-hidden bg-[#050505] border-t border-white/5"
    >
      <canvas ref={canvasRef} className="absolute inset-0 w-full h-full pointer-events-auto" />
      
      <div className="absolute bottom-12 text-center pointer-events-none">
        <span className="text-[10px] font-mono uppercase tracking-[0.3em] text-zinc-600">
          Nexus Engine
        </span>
      </div>
    </section>
  );
}





