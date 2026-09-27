"use client";

import React, { useRef, useEffect, useState } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { useGLTF, Environment, Preload, Bvh } from "@react-three/drei";
import * as THREE from "three";
import { motion, AnimatePresence } from "framer-motion";

function CuteEyes() {
  const eyesGroup = useRef<THREE.Group>(null);
  const [isBlinking, setIsBlinking] = useState(false);

  useEffect(() => {
    const blinkInterval = setInterval(() => {
      setIsBlinking(true);
      setTimeout(() => setIsBlinking(false), 150);
    }, Math.random() * 4000 + 2000);
    return () => clearInterval(blinkInterval);
  }, []);

  useFrame((state) => {
    if (eyesGroup.current) {
      const targetX = state.pointer.x * 0.15;
      const targetY = state.pointer.y * 0.15;
      eyesGroup.current.position.x = THREE.MathUtils.lerp(eyesGroup.current.position.x, targetX, 0.1);
      eyesGroup.current.position.y = THREE.MathUtils.lerp(eyesGroup.current.position.y, targetY, 0.1);
    }
  });

  const eyeScaleY = isBlinking ? 0.1 : 1;
  const nexusPrimary = "#6366f1";
  const nexusEmissive = "#4f46e5";

  return (
    <group position={[0, 0.1, 1.1]} rotation={[-0.15, 0, 0]} renderOrder={999}>
      <group ref={eyesGroup}>
        <mesh position={[-0.3, 0, 0]} scale={[1, eyeScaleY, 0.01]} renderOrder={999}>
          <capsuleGeometry args={[0.15, 0.4, 16, 32]} />
          <meshStandardMaterial 
            color={nexusPrimary} 
            emissive={nexusEmissive} 
            emissiveIntensity={4} 
            toneMapped={false} 
            depthTest={false} 
            transparent={true} 
          />
        </mesh>
        <mesh position={[0.3, 0, 0]} scale={[1, eyeScaleY, 0.01]} renderOrder={999}>
          <capsuleGeometry args={[0.15, 0.4, 16, 32]} />
          <meshStandardMaterial 
            color={nexusPrimary} 
            emissive={nexusEmissive} 
            emissiveIntensity={4} 
            toneMapped={false} 
            depthTest={false} 
            transparent={true} 
          />
        </mesh>
      </group>
    </group>
  );
}

function RobotModel() {
  const group = useRef<THREE.Group>(null);
  const { scene } = useGLTF("/models/nex.glb");

  useEffect(() => {
    scene.traverse((child) => {
      if (child.name.includes("Glitch") || child.name.includes("Glitter") || child.name === "code" || child.name.includes("Plane")) {
        child.visible = false;
      }
      if ((child as THREE.Mesh).isMesh) {
        const mesh = child as THREE.Mesh;
        if (mesh.material && (mesh.material as THREE.MeshStandardMaterial).isMeshStandardMaterial) {
          const mat = mesh.material as THREE.MeshStandardMaterial;
          mat.metalness = 0.8;
          mat.roughness = 0.3;
          mat.envMapIntensity = 1.5;
          mat.needsUpdate = true;
        }
      }
    });
  }, [scene]);

  useFrame((state) => {
    if (group.current) {
      const targetX = state.pointer.x * 0.8;
      const targetY = state.pointer.y * 0.8;
      group.current.rotation.y = THREE.MathUtils.lerp(group.current.rotation.y, targetX, 0.05);
      group.current.rotation.x = THREE.MathUtils.lerp(group.current.rotation.x, -targetY, 0.05);
      group.current.position.y = Math.sin(state.clock.elapsedTime) * 0.1 - 1.5;
    }
  });

  return (
    <group ref={group} scale={2.3}>
      <primitive object={scene} position={[0, 0, 0]} />
      <CuteEyes />
    </group>
  );
}

function Scene3D() {
  return (
    <Bvh firstHitOnly>
      <ambientLight intensity={0.8} />
      <directionalLight position={[10, 10, 5]} intensity={2} color="#ffffff" />
      <directionalLight position={[-10, -10, -5]} intensity={1} color="#6366f1" />
      <Environment preset="city" />
      <RobotModel />
      <Preload all />
    </Bvh>
  );
}

export function NEXsequence() {
  const [step, setStep] = useState(0);
  const [hasSpokenFirst, setHasSpokenFirst] = useState(false);
  const currentAudioRef = useRef<HTMLAudioElement | null>(null);

  const texts = [
    { title: "Hello, I am NEX.", desc: "I am the core intelligence of your workspace." },
    { title: "I read, analyze, and map your documents.", desc: "Scroll down to ask me anything." },
  ];

  const speak = (stepIndex: number, fallbackText: string) => {
    try {
      if (currentAudioRef.current) {
        currentAudioRef.current.pause();
        currentAudioRef.current.currentTime = 0;
      }
      const audioUrl = `/audio/nex_line${stepIndex + 1}.mp3`;
      const audio = new Audio(audioUrl);
      currentAudioRef.current = audio;

      const playPromise = audio.play();
      if (playPromise !== undefined) {
        playPromise.catch((err: Error) => {
          // NotSupportedError = audio file not found / format unsupported.
          // AbortError = play() interrupted by a subsequent call — both are expected.
          const isExpected = err.name === "NotSupportedError" || err.name === "AbortError";
          if (!isExpected) {
            console.warn("[NEX] Unexpected audio playback error:", err);
          }
          if ("speechSynthesis" in window) {
            window.speechSynthesis.cancel();
            const utterance = new SpeechSynthesisUtterance(fallbackText);
            const voices = window.speechSynthesis.getVoices();
            const preferredVoice =
              voices.find(
                (v) =>
                  v.name.includes("Google UK English Male") ||
                  v.name.includes("Microsoft Mark") ||
                  v.name.includes("Zira"),
              ) || voices[0];
            if (preferredVoice) utterance.voice = preferredVoice;
            utterance.pitch = 0.8;
            utterance.rate = 0.9;
            window.speechSynthesis.speak(utterance);
          }
        });
      }
    } catch {
      // Ignore if audio API is not available
    }
  };

  const handleClick = () => {
    if (!hasSpokenFirst) {
      setHasSpokenFirst(true);
      speak(0, texts[0].title + " " + texts[0].desc);
    } else if (step < texts.length - 1) {
      const nextStep = step + 1;
      setStep(nextStep);
      speak(nextStep, texts[nextStep].title + " " + texts[nextStep].desc);
    } else {
      window.scrollBy({ top: window.innerHeight, behavior: "smooth" });
    }
  };

  return (
    <section className="relative w-full bg-[#050505] overflow-hidden cursor-pointer" style={{ minHeight: "100svh" }} onClick={handleClick}>

      {/* DESKTOP (md+): absolute overlay with left text + right canvas */}
      <div className="hidden md:flex w-full h-full absolute inset-0">
        <div className="w-1/2 h-full flex items-center justify-start pl-20 pr-8 z-20 pointer-events-none">
          <AnimatePresence mode="wait">
            <motion.div key={step} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }} transition={{ duration: 0.5 }} className="text-left max-w-lg w-full">
              <h2 className="text-5xl lg:text-6xl font-medium tracking-tighter text-white">{texts[step].title}</h2>
              <p className="mt-4 text-xl text-zinc-400 font-light">{texts[step].desc}</p>
              {step < texts.length - 1 && (
                <div className="mt-8 text-xs font-mono uppercase tracking-[0.2em] text-indigo-400 animate-pulse flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-indigo-400 flex-shrink-0" />
                  Click to continue
                </div>
              )}
            </motion.div>
          </AnimatePresence>
        </div>
        <div className="w-1/2 h-full z-10 pointer-events-auto">
          <Canvas camera={{ position: [0, 0, 8], fov: 45 }} dpr={[1, 1.5]} performance={{ min: 0.5 }} gl={{ powerPreference: "high-performance" }} style={{ width: "100%", height: "100%" }}>
            <Scene3D />
          </Canvas>
        </div>
      </div>

      {/* MOBILE (<md): stacked column */}
      <div className="flex md:hidden flex-col w-full" style={{ minHeight: "100svh" }}>
        <div className="w-full flex-shrink-0 pointer-events-auto" style={{ height: "60svh" }}>
          <Canvas camera={{ position: [0, 0, 8], fov: 50 }} dpr={[1, 1]} performance={{ min: 0.5 }} gl={{ powerPreference: "low-power" }} style={{ width: "100%", height: "100%" }}>
            <Scene3D />
          </Canvas>
        </div>
        <div className="flex-1 flex items-center justify-start px-6 py-8 z-20 pointer-events-none">
          <AnimatePresence mode="wait">
            <motion.div key={step} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }} transition={{ duration: 0.5 }} className="text-left w-full">
              <h2 className="text-3xl sm:text-4xl font-medium tracking-tighter text-white">{texts[step].title}</h2>
              <p className="mt-3 text-base text-zinc-400 font-light">{texts[step].desc}</p>
              {step < texts.length - 1 && (
                <div className="mt-6 text-[10px] font-mono uppercase tracking-[0.2em] text-indigo-400 animate-pulse flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-indigo-400 flex-shrink-0" />
                  {!hasSpokenFirst ? "Tap to initialize Voice" : "Tap to continue"}
                </div>
              )}
            </motion.div>
          </AnimatePresence>
        </div>
      </div>

    </section>
  );
}


