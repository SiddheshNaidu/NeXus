"use client";

import React, { useEffect, useRef, useState, useMemo } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import * as THREE from 'three';

const VOXEL_LETTERS = {
  N: [[1,0,0,0,1],[1,1,0,0,1],[1,0,1,0,1],[1,0,0,1,1],[1,0,0,0,1]],
  E: [[1,1,1,1,1],[1,0,0,0,0],[1,1,1,0,0],[1,0,0,0,0],[1,1,1,1,1]],
  X: [[1,0,0,0,1],[0,1,0,1,0],[0,0,1,0,0],[0,1,0,1,0],[1,0,0,0,1]],
  U: [[1,0,0,0,1],[1,0,0,0,1],[1,0,0,0,1],[1,0,0,0,1],[0,1,1,1,0]],
  S: [[0,1,1,1,1],[1,0,0,0,0],[0,1,1,1,0],[0,0,0,0,1],[1,1,1,1,0]]
};

function VoxelCube({ x, y, size, spacing, isLoaded }: { x: number; y: number; size: number; spacing: number; isLoaded: boolean }) {
  const meshRef = useRef<THREE.Mesh>(null);
  const rotSpeed = useMemo(() => ({
    x: (Math.random() - 0.5) * 2,
    y: (Math.random() - 0.5) * 2.5,
    z: (Math.random() - 0.5) * 1.5,
  }), []);

  useFrame((_, delta) => {
    if (!meshRef.current) return;
    if (!isLoaded) {
      meshRef.current.rotation.x += delta * rotSpeed.x;
      meshRef.current.rotation.y += delta * rotSpeed.y;
      meshRef.current.rotation.z += delta * rotSpeed.z;
    } else {
      meshRef.current.rotation.x = THREE.MathUtils.lerp(meshRef.current.rotation.x, 0, 0.1);
      meshRef.current.rotation.y = THREE.MathUtils.lerp(meshRef.current.rotation.y, 0, 0.1);
      meshRef.current.rotation.z = THREE.MathUtils.lerp(meshRef.current.rotation.z, 0, 0.1);
    }
  });

  return (
    <mesh ref={meshRef} position={[(x - 2) * spacing, (2 - y) * spacing, 0]}>
      <boxGeometry args={[size, size, size]} />
      <meshStandardMaterial color="#ffffff" emissive="#ffffff" emissiveIntensity={0.2} metalness={0.8} roughness={0.2} />
    </mesh>
  );
}

function VoxelLetter({ grid, offset, isLoaded, onFadeOut }: { grid: number[][]; offset: number; isLoaded: boolean; onFadeOut: boolean }) {
  const groupRef = useRef<THREE.Group>(null);

  useFrame((_, delta) => {
    if (!groupRef.current) return;
    if (onFadeOut) {
      groupRef.current.position.z += delta * 5;
      groupRef.current.scale.multiplyScalar(0.9);
    }
  });

  const size = 0.2;
  const spacing = 0.22;
  const cubes = [];

  for (let row = 0; row < 5; row++) {
    for (let col = 0; col < 5; col++) {
      if (grid[row][col]) {
        cubes.push(<VoxelCube key={`${col}-${row}`} x={col} y={row} size={size} spacing={spacing} isLoaded={isLoaded} />);
      }
    }
  }

  return <group ref={groupRef} position={[offset, 0, 0]}>{cubes}</group>;
}

function PreloaderScene({ isLoaded, onComplete }: { isLoaded: boolean; onComplete: () => void }) {
  const [fadeOut, setFadeOut] = useState(false);
  const { camera, size } = useThree();

  useEffect(() => {
    const aspect = size.width / size.height;
    camera.position.z = Math.max(5, 8.5 / aspect);
  }, [size, camera]);

  useEffect(() => {
    if (!isLoaded) return;
    const t1 = setTimeout(() => setFadeOut(true), 1500);
    const t2 = setTimeout(() => onComplete(), 2500);
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, [isLoaded, onComplete]);

  const letterSpacing = 1.5;
  const offsets = [-2, -1, 0, 1, 2].map(n => n * letterSpacing);
  const letters = [VOXEL_LETTERS.N, VOXEL_LETTERS.E, VOXEL_LETTERS.X, VOXEL_LETTERS.U, VOXEL_LETTERS.S];

  return (
    <>
      <ambientLight intensity={0.5} />
      <directionalLight position={[5, 5, 5]} intensity={2} color="#6366f1" />
      <directionalLight position={[-5, -5, -5]} intensity={1} color="#ffffff" />
      <group position={[0, 0, -2]}>
        {letters.map((grid, i) => (
          <VoxelLetter key={i} grid={grid} offset={offsets[i]} isLoaded={isLoaded} onFadeOut={fadeOut} />
        ))}
      </group>
    </>
  );
}

const SESSION_KEY = "nexus_preloader_done";

export function NexusPreloader({ children }: { children: React.ReactNode }) {
  const [isAnimating, setIsAnimating] = useState(true);
  const [isLoaded, setIsLoaded] = useState(false);

  useEffect(() => {
    // Single consistent key check
    const done = typeof window !== "undefined" && sessionStorage.getItem(SESSION_KEY);
    if (done) {
      setIsAnimating(false);
      return;
    }
    // Auto-resolve after 800ms if WebGL loads fast (no useProgress dependency)
    const t = setTimeout(() => setIsLoaded(true), 800);
    return () => clearTimeout(t);
  }, []);

  const handleComplete = () => {
    if (typeof window !== "undefined") {
      sessionStorage.setItem(SESSION_KEY, "true");
    }
    setIsAnimating(false);
  };

  if (!isAnimating) return <>{children}</>;

  return (
    <div className="fixed inset-0 z-[9999] bg-[#050505]">
      <div className="absolute inset-0 w-full h-full z-10 pointer-events-none">
        <Canvas camera={{ position: [0, 0, 5], fov: 45 }} dpr={[1, 1.5]} gl={{ powerPreference: "high-performance" }}>
          <PreloaderScene isLoaded={isLoaded} onComplete={handleComplete} />
        </Canvas>
      </div>
      <div className="opacity-0 pointer-events-none fixed inset-0 w-full h-full overflow-hidden" style={{ visibility: "hidden" }}>
        {children}
      </div>
    </div>
  );
}
