"use client";

import * as React from "react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useGSAP } from "@gsap/react";

if (typeof window !== "undefined") {
  gsap.registerPlugin(ScrollTrigger, useGSAP);
}

export function StorySection() {
  const containerRef = React.useRef<HTMLElement>(null);
  const videoWrapperRef = React.useRef<HTMLDivElement>(null);
  const textContainerRef = React.useRef<HTMLDivElement>(null);

  useGSAP(() => {
    const isMobile = window.innerWidth < 768;

    if (isMobile) {
      // Mobile: Fluid scroll without lock-pinning
      const tl = gsap.timeline({
        scrollTrigger: {
          trigger: containerRef.current,
          start: "top 80%",
          end: "bottom 20%",
          scrub: 1,
        },
      });

      tl.to(videoWrapperRef.current, {
        opacity: 0.15,
        duration: 1,
        ease: "power1.inOut",
      }, 0);

      tl.fromTo(
        ".story-sentence",
        { opacity: 0, y: 30 },
        { opacity: 1, y: 0, stagger: 0.2, ease: "power2.out" },
        0.2
      );
    } else {
      // Desktop: Cinematic pinned timeline
      const tl = gsap.timeline({
        scrollTrigger: {
          trigger: containerRef.current,
          start: "top top",
          end: "+=150%",
          pin: window.innerWidth >= 768,
          scrub: 1.2,
        },
      });

      tl.to(videoWrapperRef.current, {
        opacity: 0.1,
        duration: 1.5,
        ease: "power1.inOut",
      }, 0);

      tl.fromTo(
        ".story-sentence",
        { opacity: 0, y: 60, scale: 0.98 },
        { opacity: 1, y: 0, scale: 1, duration: 2, stagger: 0.4, ease: "power3.out" },
        0.3
      );
    }
  }, { scope: containerRef });

  return (
    <section ref={containerRef} className="relative min-h-[80vh] md:h-screen w-full border-t border-white/5 overflow-hidden bg-[#050505] py-20 md:py-0">
      {/* Background wrapper (video + overlays) */}
      <div ref={videoWrapperRef} className="absolute inset-0 w-full h-full opacity-[0.85]">
        <video
          autoPlay
          loop
          muted
          playsInline
          className="absolute inset-0 h-full w-full object-cover mix-blend-luminosity"
          src="https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260405_170732_8a9ccda6-5cff-4628-b164-059c500a2b41.mp4"
        />

        {/* CSS-based Noise overlay */}
        <div 
          className="pointer-events-none absolute inset-0 opacity-[0.4] mix-blend-overlay" 
          style={{
            backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E")`
          }}
        />

        {/* Gradient overlays to seamlessly blend with the #050505 background */}
        <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-[#050505] via-transparent to-[#050505]" />
        <div className="pointer-events-none absolute inset-0 bg-gradient-to-r from-[#050505]/60 via-transparent to-[#050505]/60" />
      </div>

      {/* NEXUS Editorial Content */}
      <div ref={textContainerRef} className="relative z-10 flex h-full flex-col items-center justify-center px-6 text-center">
        <div className="story-sentence inline-flex items-center gap-3 border-b border-white/10 pb-4 mb-6 md:mb-8">
          <div className="h-1.5 w-1.5 bg-indigo-500" />
          <span className="text-[10px] md:text-xs font-mono uppercase tracking-[0.3em] text-zinc-500">
            The NEXUS Philosophy
          </span>
        </div>

        <h2 className="story-sentence text-3xl sm:text-4xl md:text-5xl lg:text-6xl font-medium tracking-tighter text-zinc-50 max-w-4xl leading-[1.1]">
          An answer is more useful when you can <br className="hidden md:block" />
          <span className="text-zinc-500">inspect why it is true.</span>
        </h2>

        <p className="story-sentence mt-6 md:mt-8 max-w-2xl text-base md:text-lg text-zinc-400 font-light leading-relaxed">
          NEXUS does not just synthesize information. It preserves the unbreakable link between the claim and the source document. Every response is anchored in physical proof.
        </p>
      </div>
    </section>
  );
}

