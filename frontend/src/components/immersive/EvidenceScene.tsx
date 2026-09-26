"use client";

import * as React from "react";
import * as THREE from "three";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Edges } from "@react-three/drei";

// Small utility to animate values smoothly
function damp(current: number, target: number, lambda: number, dt: number) {
  return THREE.MathUtils.damp(current, target, lambda, dt);
}

const ACTIVE_COLOR = new THREE.Color("#6366f1");
const NEUTRAL_COLOR = new THREE.Color("#ffffff");

// 
// DOCUMENT PLANE COMPONENT
//
function DocumentPlane({ 
  position, 
  dimensions,
  isActive,
  isBackground,
  reducedMotion,
  baseEdgeOpacity,
  floatSpeed
}: { 
  position: [number, number, number],
  dimensions: [number, number],
  isActive: boolean,
  isBackground: boolean,
  reducedMotion: boolean,
  baseEdgeOpacity: number,
  floatSpeed: number
}) {
  const meshRef = React.useRef<THREE.Mesh>(null);
  const materialRef = React.useRef<THREE.MeshBasicMaterial>(null);
  const edgesMaterialRef = React.useRef<THREE.LineBasicMaterial>(null);
  const markerMaterialRef = React.useRef<THREE.MeshBasicMaterial>(null);
  const markerEdgesRef = React.useRef<THREE.LineBasicMaterial>(null);
  
  // Starting state
  const startY = position[1];
  
  useFrame((state, delta) => {
    if (!meshRef.current || !materialRef.current || !edgesMaterialRef.current || !markerMaterialRef.current || !markerEdgesRef.current) return;
    
    // Calculate targets based on state
    let targetZ = position[2];
    let targetY = position[1];
    
    // B-4: Improved idle depth hierarchy
    let targetOpacity = isBackground ? (isActive ? 0.05 : 0.15) : (isActive ? 0.9 : 0.3);
    let targetEdgeOpacity = isBackground ? (isActive ? 0.02 : baseEdgeOpacity) : (isActive ? 0.6 : baseEdgeOpacity);
    
    // B-2: Evidence marker target opacities (0 when idle)
    const targetMarkerOpacity = isActive ? 0.15 : 0.0;
    const targetMarkerEdgeOpacity = isActive ? 0.5 : 0.0;
    
    // Idle float (only if not reduced motion and not strictly active)
    if (!reducedMotion && !isActive && !isBackground) {
      targetY = startY + Math.sin(state.clock.elapsedTime * floatSpeed) * 0.1;
    }
    
    // Active state translation
    if (isActive) {
      targetZ = position[2] + 0.5; // pull forward slightly
    } else if (!isBackground && !isActive) {
      targetZ = position[2];
    }
    
    // B-5: Edge color transition target
    const targetColor = isActive ? ACTIVE_COLOR : NEUTRAL_COLOR;

    if (reducedMotion) {
      // Instant snap
      meshRef.current.position.z = targetZ;
      meshRef.current.position.y = targetY;
      materialRef.current.opacity = targetOpacity;
      edgesMaterialRef.current.opacity = targetEdgeOpacity;
      markerMaterialRef.current.opacity = targetMarkerOpacity;
      markerEdgesRef.current.opacity = targetMarkerEdgeOpacity;
      edgesMaterialRef.current.color.copy(targetColor);
    } else {
      // Smooth interpolation
      meshRef.current.position.z = damp(meshRef.current.position.z, targetZ, 4, delta);
      meshRef.current.position.y = damp(meshRef.current.position.y, targetY, 2, delta);
      materialRef.current.opacity = damp(materialRef.current.opacity, targetOpacity, 4, delta);
      edgesMaterialRef.current.opacity = damp(edgesMaterialRef.current.opacity, targetEdgeOpacity, 4, delta);
      
      // B-2: Animate evidence marker opacity
      markerMaterialRef.current.opacity = damp(markerMaterialRef.current.opacity, targetMarkerOpacity, 4, delta);
      markerEdgesRef.current.opacity = damp(markerEdgesRef.current.opacity, targetMarkerEdgeOpacity, 4, delta);
      
      // B-5: Smooth edge color lerp
      edgesMaterialRef.current.color.lerp(targetColor, delta * 4);
    }
  });

  return (
    <mesh ref={meshRef} position={position}>
      <planeGeometry args={dimensions} />
      <meshBasicMaterial 
        ref={materialRef}
        color={isActive ? "#0a0a0a" : "#050505"} 
        transparent 
        opacity={0.3}
        depthWrite={false}
      />
      <Edges>
        <lineBasicMaterial 
          ref={edgesMaterialRef}
          color="#ffffff" 
          transparent 
          opacity={0.2} 
        />
      </Edges>
      
      {/* B-2: Always mounted Evidence Highlight Marker */}
      <mesh position={[-0.3, 0.4, 0.01]}>
        <planeGeometry args={[1.2, 0.2]} />
        <meshBasicMaterial ref={markerMaterialRef} color="#6366f1" transparent opacity={0} depthWrite={false} />
        <Edges>
          <lineBasicMaterial ref={markerEdgesRef} color="#6366f1" transparent opacity={0} />
        </Edges>
      </mesh>
    </mesh>
  );
}

//
// CONNECTION LINE COMPONENT
//
function ConnectionLine({ 
  isActive, 
  reducedMotion,
  anchorRef
}: { 
  isActive: boolean, 
  reducedMotion: boolean,
  anchorRef?: React.RefObject<HTMLElement | null>
}) {
  const materialRef = React.useRef<THREE.LineBasicMaterial>(null);
  const lineRef = React.useRef<THREE.Line>(null);
  const progress = React.useRef(0);
  const { size, viewport, gl } = useThree();
  
  // Create geometry once
  const geometry = React.useMemo(() => {
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(51 * 3), 3));
    return geo;
  }, []);
  
  useFrame((_, delta) => {
    if (!materialRef.current || !lineRef.current) return;
    
    const targetProgress = isActive ? 1 : 0;
    if (reducedMotion) {
      progress.current = targetProgress;
    } else {
      progress.current = damp(progress.current, targetProgress, 6, delta);
    }
    materialRef.current.opacity = progress.current * 0.8;
    
    // Dynamic Anchor Calculation
    let webglY = 0;
    if (anchorRef?.current) {
      const anchorRect = anchorRef.current.getBoundingClientRect();
      const canvasRect = gl.domElement.getBoundingClientRect();
      const pixelsY = (anchorRect.top + anchorRect.height / 2) - (canvasRect.top + canvasRect.height / 2);
      webglY = - (pixelsY / size.height) * viewport.height;
    }
    
    const start = new THREE.Vector3(-viewport.width / 2, webglY, 0);
    const end = new THREE.Vector3(-0.3, 0.4, 0.5);
    const mid = new THREE.Vector3(-viewport.width / 4, (webglY + 0.4) / 2, 0.25);
    
    const curve = new THREE.QuadraticBezierCurve3(start, mid, end);
    const points = curve.getPoints(50);
    
    const positions = lineRef.current.geometry.attributes.position.array as Float32Array;
    for (let i = 0; i < points.length; i++) {
      positions[i * 3] = points[i].x;
      positions[i * 3 + 1] = points[i].y;
      positions[i * 3 + 2] = points[i].z;
    }
    lineRef.current.geometry.attributes.position.needsUpdate = true;
  });

    const lineObj = React.useMemo(() => {
    return new THREE.Line(
      geometry,
      new THREE.LineBasicMaterial({ color: "#6366f1", transparent: true, opacity: 0 })
    );
  }, [geometry]);

  React.useEffect(() => {
    lineRef.current = lineObj;
    materialRef.current = lineObj.material as THREE.LineBasicMaterial;
  }, [lineObj]);

  return <primitive object={lineObj} />;
}

//
// MAIN SCENE
//
function SceneContents({ isActive, reducedMotion, anchorRef }: { isActive: boolean, reducedMotion: boolean, anchorRef?: React.RefObject<HTMLElement | null> }) {
  useFrame((state, delta) => {
    // Subtle camera shift on activation
    const targetZ = isActive ? 4.5 : 5;
    const targetX = isActive ? 0.2 : 0;
    
    if (reducedMotion) {
      state.camera.position.z = targetZ;
      state.camera.position.x = targetX;
    } else {
      state.camera.position.z = damp(state.camera.position.z, targetZ, 3, delta);
      state.camera.position.x = damp(state.camera.position.x, targetX, 3, delta);
    }
  });

  return (
    <>
      <ambientLight intensity={0.1} />
      
      {/* Far Background Plane */}
      <DocumentPlane 
        position={[1.5, -0.6, -2]} 
        dimensions={[1.4, 2.0]}
        isActive={false} 
        isBackground={true} 
        reducedMotion={reducedMotion}
        baseEdgeOpacity={0.05}
        floatSpeed={0.4}
      />
      
      {/* Mid Background Plane */}
      <DocumentPlane 
        position={[-1.2, 0.4, -1]} 
        dimensions={[1.7, 2.4]}
        isActive={false} 
        isBackground={true} 
        reducedMotion={reducedMotion}
        baseEdgeOpacity={0.10}
        floatSpeed={0.3}
      />
      
      {/* Focal Document */}
      <DocumentPlane 
        position={[0, 0, 0]} 
        dimensions={[2.0, 2.8]}
        isActive={isActive} 
        isBackground={false} 
        reducedMotion={reducedMotion}
        baseEdgeOpacity={0.20}
        floatSpeed={0.5}
      />
      
      {/* Provenance Connection */}
      <ConnectionLine isActive={isActive} reducedMotion={reducedMotion} anchorRef={anchorRef} />
    </>
  );
}

//
// FALLBACK EXPORTED COMPONENT
//
export function EvidenceScene({ 
  isActive, 
  reducedMotion,
  anchorRef
}: { 
  isActive: boolean, 
  reducedMotion: boolean,
  anchorRef?: React.RefObject<HTMLElement | null>
}) {
  return (
    <div className="w-full h-full relative">
      <Canvas 
        camera={{ position: [0, 0, 5], fov: 45 }}
        gl={{ antialias: true, alpha: true, powerPreference: "low-power" }}
        dpr={[1, 2]}
      >
        <React.Suspense fallback={null}>
          <SceneContents isActive={isActive} reducedMotion={reducedMotion} anchorRef={anchorRef} />
        </React.Suspense>
      </Canvas>
    </div>
  );
}