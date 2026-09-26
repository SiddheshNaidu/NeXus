"use client";

import React, { useEffect, useRef, useState, useMemo } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { useProgress } from '@react-three/drei';
import * as THREE from 'three';

const VOXEL_LETTERS = {
  N: [
    [1,0,0,0,1],
    [1,1,0,0,1],
    [1,0,1,0,1],
    [1,0,0,1,1],
    [1,0,0,0,1]
  ],
  E: [
    [1,1,1,1,1],
    [1,0,0,0,0],
    [1,1,1,0,0],
    [1,0,0,0,0],
    [1,1,1,1,1]
  ],
  X: [
    [1,0,0,0,1],
    [0,1,0,1,0],
    [0,0,1,0,0],
    [0,1,0,1,0],
    [1,0,0,0,1]
  ],
  U: [
    [1,0,0,0,1],
    [1,0,0,0,1],
    [1,0,0,0,1],
    [1,0,0,0,1],
    [0,1,1,1,0]
  ],
  S: [
    [0,1,1,1,1],
    [1,0,0,0,0],
    [0,1,1,1,0],
    [0,0,0,0,1],
    [1,1,1,1,0]
  ]
};

function VoxelCube({ x, y, size, spacing, isLoaded }: { x: number, y: number, size: number, spacing: number, isLoaded: boolean }) {
    const meshRef = useRef<THREE.Mesh>(null);
    
    // Each block has random rotation speeds
    const rotSpeed = useMemo(() => ({
        x: (Math.random() - 0.5) * 2,
        y: (Math.random() - 0.5) * 2.5,
        z: (Math.random() - 0.5) * 1.5
    }), []);

    useFrame((state, delta) => {
        if (!meshRef.current) return;
        
        if (!isLoaded) {
            // Rotate each block individually in random directions
            meshRef.current.rotation.x += delta * rotSpeed.x;
            meshRef.current.rotation.y += delta * rotSpeed.y;
            meshRef.current.rotation.z += delta * rotSpeed.z;
        } else {
            // Smoothly snap back to 0 rotation
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

function VoxelLetter({ grid, offset, isLoaded, onFadeOut }: { grid: number[][], offset: number, isLoaded: boolean, onFadeOut: boolean }) {
    const groupRef = useRef<THREE.Group>(null);
    
    useFrame((state, delta) => {
        if (!groupRef.current) return;

        if (onFadeOut) {
            // Scatter outwards and shrink the whole letter (End Animation as requested)
            groupRef.current.position.z += delta * 5;
            groupRef.current.scale.multiplyScalar(0.9);
        }
    });

    const cubes = [];
    const size = 0.2;
    const spacing = 0.22;

    for (let y = 0; y < 5; y++) {
        for (let x = 0; x < 5; x++) {
            if (grid[y][x]) {
                cubes.push(
                    <VoxelCube key={`${x}-${y}`} x={x} y={y} size={size} spacing={spacing} isLoaded={isLoaded} />
                );
            }
        }
    }

    return (
        <group ref={groupRef} position={[offset, 0, 0]}>
            {cubes}
        </group>
    );
}

function PreloaderScene({ isLoaded, onComplete }: { isLoaded: boolean, onComplete: () => void }) {
    const [fadeOut, setFadeOut] = useState(false);

    useEffect(() => {
        if (isLoaded) {
            // Once loaded, wait for the lerp snap to finish (1.5s), then trigger fade out scatter
            const t1 = setTimeout(() => {
                setFadeOut(true);
            }, 1500);
            
            // Unmount preloader completely
            const t2 = setTimeout(() => {
                onComplete();
            }, 2500);

            return () => {
                clearTimeout(t1);
                clearTimeout(t2);
            };
        }
    }, [isLoaded, onComplete]);

    const letterSpacing = 1.5;
    const offsets = [-2 * letterSpacing, -1 * letterSpacing, 0, 1 * letterSpacing, 2 * letterSpacing];
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

export function NexusPreloader({ children }: { children: React.ReactNode }) {
  const [isAnimating, setIsAnimating] = useState(true);
  const { active, progress } = useProgress();
  const [isLoaded, setIsLoaded] = useState(false);

  useEffect(() => {
      const hasVisited = typeof window !== "undefined" ? sessionStorage.getItem("nexus_preloader_seen") : null;
      if (hasVisited) {
          setIsAnimating(false);
          return;
      }
      
      sessionStorage.setItem('nexus_preloader_shown', '1');
      if (progress === 100 || !active) {
          const t = setTimeout(() => {
              setIsLoaded(true);
          }, 500);
          return () => clearTimeout(t);
      }
  }, [progress, active]);

  const handleComplete = () => {
      if (typeof window !== "undefined") {
          sessionStorage.setItem("nexus_preloader_seen", "true");
      }
      setIsAnimating(false);
  };

  if (!isAnimating) return <>{children}</>;

  return (
    <div className="fixed inset-0 z-[9999] bg-[#050505]">
      {/* 3D Sci-Fi Preloader */}
      <div className="absolute inset-0 w-full h-full z-10 pointer-events-none">
          <Canvas camera={{ position: [0, 0, 5], fov: 45 }} dpr={[1, 1.5]} gl={{ powerPreference: "high-performance" }}>
              <PreloaderScene isLoaded={isLoaded} onComplete={handleComplete} />
          </Canvas>
      </div>

      {/* Render children hidden so they can preload in the background */}
      <div className="opacity-0 pointer-events-none fixed inset-0 w-full h-full overflow-hidden" style={{ visibility: 'hidden' }}>
          {children}
      </div>
    </div>
  );
}

