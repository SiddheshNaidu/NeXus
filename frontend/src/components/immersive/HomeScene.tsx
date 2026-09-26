"use client";

import * as React from "react";
import * as THREE from "three";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Html, Text } from "@react-three/drei";
import { DocumentSource } from "@/services/types";
import { NexModel } from "./NexModel";
import { useReducedMotion } from "motion/react";

function damp(current: number, target: number, lambda: number, dt: number, reducedMotion: boolean) {
  if (reducedMotion) return target;
  return THREE.MathUtils.damp(current, target, lambda, dt);
}

const PALETTE = {
  bg: new THREE.Color("#050505"),
  docIdle: new THREE.Color("#111113"),
  docHover: new THREE.Color("#1f1f22"),
  line: new THREE.Color("#6366f1"),
  textDim: new THREE.Color("#52525b"),
  textBright: new THREE.Color("#f4f4f5")
};

function DocumentNode({
  doc,
  index,
  total,
  hoveredId,
  setHoveredId,
  reducedMotion,
  isTransitioning
}: {
  doc: DocumentSource;
  index: number;
  total: number;
  hoveredId: string | null;
  setHoveredId: (id: string | null) => void;
  reducedMotion: boolean;
  isTransitioning: boolean;
}) {
  const meshRef = React.useRef<THREE.Mesh>(null);
  const materialRef = React.useRef<THREE.MeshBasicMaterial>(null);
  
  // Distribute documents in a sparse field
  const angle = (index / total) * Math.PI * 2;
  const radius = 3 + Math.random() * 2;
  const initialPos = React.useMemo(() => new THREE.Vector3(
    Math.cos(angle) * radius,
    (Math.random() - 0.5) * 4,
    (Math.random() - 0.5) * 2 - 2
  ), [angle, radius]);

  const isHovered = hoveredId === doc.id;
  const isOtherHovered = hoveredId !== null && hoveredId !== doc.id;

  useFrame((state, delta) => {
    if (!meshRef.current || !materialRef.current) return;

    // Subtle floating
    if (!reducedMotion) {
      const time = state.clock.elapsedTime;
      const yOffset = Math.sin(time * 0.5 + index) * 0.2;
      meshRef.current.position.y = damp(
        meshRef.current.position.y,
        initialPos.y + (isHovered ? 0.5 : yOffset),
        4,
        delta,
        reducedMotion
      );
    }

    // Scale & Depth
    const targetZ = isTransitioning ? initialPos.z + 10 : (isHovered ? initialPos.z + 2 : (isOtherHovered ? initialPos.z - 1 : initialPos.z));
    meshRef.current.position.z = damp(meshRef.current.position.z, targetZ, 4, delta, reducedMotion);
    
    const targetScale = isTransitioning ? 0 : (isHovered ? 1.2 : (isOtherHovered ? 0.9 : 1.0));
    meshRef.current.scale.setScalar(damp(meshRef.current.scale.x, targetScale, 6, delta, reducedMotion));

    // Colors
    const targetColor = isHovered ? PALETTE.docHover : PALETTE.docIdle;
    materialRef.current.color.lerp(targetColor, reducedMotion ? 1 : delta * 5);
    
    const targetOpacity = isTransitioning ? 0 : (isOtherHovered ? 0.3 : 0.9);
    materialRef.current.opacity = damp(materialRef.current.opacity, targetOpacity, 4, delta, reducedMotion);
  });

  return (
    <group position={initialPos}>
      <mesh
        ref={meshRef}
        onPointerOver={(e) => { e.stopPropagation(); setHoveredId(doc.id); }}
        onPointerOut={() => setHoveredId(null)}
      >
        <planeGeometry args={[1.5, 2]} />
        <meshBasicMaterial 
          ref={materialRef} 
          color={PALETTE.docIdle} 
          transparent 
          opacity={0.9} 
          side={THREE.DoubleSide}
          depthWrite={false}
        />
        <lineSegments>
          <edgesGeometry args={[new THREE.PlaneGeometry(1.5, 2)]} />
          <lineBasicMaterial color={new THREE.Color("#ffffff")} transparent opacity={isHovered ? 0.3 : 0.1} />
        </lineSegments>
      </mesh>
      
      {/* Metadata HTML Overlay */}
      <Html
        position={[0, 0, 0.1]}
        center
        className="pointer-events-none"
        style={{ opacity: isTransitioning ? 0 : (isHovered ? 1 : 0),
          transform: `scale(${isHovered ? 1 : 0.8})`,
          transition: 'all 0.3s cubic-bezier(0.16, 1, 0.3, 1)'
        }}
      >
        <div className="w-48 p-3 bg-[#050505]/95 backdrop-blur-md border border-white/10 shadow-2xl">
          <div className="text-[10px] font-mono text-zinc-500 mb-2 uppercase tracking-widest">{doc.id}</div>
          <div className="text-xs font-medium text-zinc-300 leading-tight line-clamp-2">{doc.filename}</div>
          <div className="mt-3 flex items-center justify-between">
            <div className="text-[9px] font-mono tracking-widest text-indigo-400">{doc.status}</div>
          </div>
        </div>
      </Html>
    </group>
  );
}

function ConnectionLines({ hoveredId }: { hoveredId: string | null }) {
  const lineRef = React.useRef<THREE.Line>(null);
  const geoRef = React.useRef<THREE.BufferGeometry>(null);
  
  const points = React.useMemo(() => new Float32Array(50 * 3), []);

  useFrame((state) => {
    if (!lineRef.current || !geoRef.current) return;
    
    const mat = lineRef.current.material as THREE.LineBasicMaterial;
    if (!hoveredId) {
      mat.opacity = THREE.MathUtils.damp(mat.opacity, 0, 8, 1/60);
      return;
    }

    mat.opacity = THREE.MathUtils.damp(mat.opacity, 0.6, 8, 1/60);
    
    // Animate curve from a generic position representing the hovered doc towards bottom center (CTA)
    const startPt = new THREE.Vector3(0, 0, -2);
    const endPt = new THREE.Vector3(0, -state.viewport.height / 2 + 1, 0); // Bottom center towards CTA
    
    const controlPt = new THREE.Vector3(
      (startPt.x + endPt.x) / 2,
      startPt.y,
      (startPt.z + endPt.z) / 2
    );
    
    const curve = new THREE.QuadraticBezierCurve3(startPt, controlPt, endPt);
    const curvePoints = curve.getPoints(49);
    
    for (let i = 0; i < curvePoints.length; i++) {
      points[i * 3] = curvePoints[i].x;
      points[i * 3 + 1] = curvePoints[i].y;
      points[i * 3 + 2] = curvePoints[i].z;
    }
    
    geoRef.current.setAttribute('position', new THREE.BufferAttribute(points, 3));
    geoRef.current.attributes.position.needsUpdate = true;
  });

  const lineObj = React.useMemo(() => {
    const geo = new THREE.BufferGeometry();
    const mat = new THREE.LineBasicMaterial({ color: PALETTE.line, transparent: true, opacity: 0 });
    const line = new THREE.Line(geo, mat);
    return line;
  }, []);

  // Update refs manually since we use primitive
  React.useEffect(() => {
    lineRef.current = lineObj;
    geoRef.current = lineObj.geometry;
  }, [lineObj]);

  return <primitive object={lineObj} />;
}

export function HomeScene({ docs, isTransitioning }: { docs: DocumentSource[]; isTransitioning: boolean }) {
  const [hoveredId, setHoveredId] = React.useState<string | null>(null);
  const reducedMotion = useReducedMotion() ?? false;

  return (
    <Canvas camera={{ position: [0, 0, 8], fov: 45 }} dpr={[1, 2]}>
      <ambientLight intensity={0.5} />
      <React.Suspense fallback={null}>
        <NexModel position={[0, 0, 0]} />
      </React.Suspense>
      {docs.map((doc, i) => (
        <DocumentNode 
          key={doc.id} 
          doc={doc} 
          index={i} 
          total={docs.length}
          hoveredId={hoveredId}
          setHoveredId={setHoveredId}
          reducedMotion={reducedMotion}
          isTransitioning={isTransitioning}
        />
      ))}
      <ConnectionLines hoveredId={hoveredId} />
    </Canvas>
  );
}

