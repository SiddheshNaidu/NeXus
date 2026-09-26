import React, { useRef, useState, useEffect } from 'react'
import { useGLTF, Html } from '@react-three/drei'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import { gsap } from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import { useAudioReactive } from '@/hooks/useAudioReactive'

export function NexModel(props: any) {
  const group = useRef<THREE.Group>(null)
  const { scene } = useGLTF('/models/nex.glb')
  const { isListening, startListening, getAudioLevel } = useAudioReactive()
  
  // Custom uniform for our fluid vertex shader
  const uniforms = useRef({
      uTime: { value: 0 },
      uAudio: { value: 0 },
  })

  useEffect(() => {
    scene.traverse((child) => {
      if ((child as THREE.Mesh).isMesh) {
        const mesh = child as THREE.Mesh;
        
        // Premium glass material
        const material = new THREE.MeshPhysicalMaterial({
            color: new THREE.Color("#ffffff"),
            emissive: new THREE.Color("#4f46e5"),
            emissiveIntensity: 0.5,
            metalness: 0.8,
            roughness: 0.2,
            transmission: 1, 
            thickness: 1.5,
            ior: 1.5,
        });

        // The Magic: We inject custom GLSL to make the static GLB breathe and distort organically
        // This mimics the fluid soft-body motion design of the Locomotive site
        material.onBeforeCompile = (shader) => {
            shader.uniforms.uTime = uniforms.current.uTime;
            shader.uniforms.uAudio = uniforms.current.uAudio;

            shader.vertexShader = `
              uniform float uTime;
              uniform float uAudio;
              
              // Simplex 3D Noise function for organic distortion
              vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
              vec4 mod289(vec4 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
              vec4 permute(vec4 x) { return mod289(((x*34.0)+1.0)*x); }
              vec4 taylorInvSqrt(vec4 r) { return 1.79284291400159 - 0.85373472095314 * r; }
              float snoise(vec3 v) {
                const vec2  C = vec2(1.0/6.0, 1.0/3.0) ;
                const vec4  D = vec4(0.0, 0.5, 1.0, 2.0);
                vec3 i  = floor(v + dot(v, C.yyy) );
                vec3 x0 = v - i + dot(i, C.xxx) ;
                vec3 g = step(x0.yzx, x0.xyz);
                vec3 l = 1.0 - g;
                vec3 i1 = min( g.xyz, l.zxy );
                vec3 i2 = max( g.xyz, l.zxy );
                vec3 x1 = x0 - i1 + C.xxx;
                vec3 x2 = x0 - i2 + C.yyy;
                vec3 x3 = x0 - D.yyy;
                i = mod289(i);
                vec4 p = permute( permute( permute(
                           i.z + vec4(0.0, i1.z, i2.z, 1.0 ))
                         + i.y + vec4(0.0, i1.y, i2.y, 1.0 ))
                         + i.x + vec4(0.0, i1.x, i2.x, 1.0 ));
                float n_ = 0.142857142857;
                vec3  ns = n_ * D.wyz - D.xzx;
                vec4 j = p - 49.0 * floor(p * ns.z * ns.z);
                vec4 x_ = floor(j * ns.z);
                vec4 y_ = floor(j - 7.0 * x_ );
                vec4 x = x_ *ns.x + ns.yyyy;
                vec4 y = y_ *ns.x + ns.yyyy;
                vec4 h = 1.0 - abs(x) - abs(y);
                vec4 b0 = vec4( x.xy, y.xy );
                vec4 b1 = vec4( x.zw, y.zw );
                vec4 s0 = floor(b0)*2.0 + 1.0;
                vec4 s1 = floor(b1)*2.0 + 1.0;
                vec4 sh = -step(h, vec4(0.0));
                vec4 a0 = b0.xzyw + s0.xzyw*sh.xxyy ;
                vec4 a1 = b1.xzyw + s1.xzyw*sh.zzww ;
                vec3 p0 = vec3(a0.xy,h.x);
                vec3 p1 = vec3(a0.zw,h.y);
                vec3 p2 = vec3(a1.xy,h.z);
                vec3 p3 = vec3(a1.zw,h.w);
                vec4 norm = taylorInvSqrt(vec4(dot(p0,p0), dot(p1,p1), dot(p2, p2), dot(p3,p3)));
                p0 *= norm.x;
                p1 *= norm.y;
                p2 *= norm.z;
                p3 *= norm.w;
                vec4 m = max(0.6 - vec4(dot(x0,x0), dot(x1,x1), dot(x2,x2), dot(x3,x3)), 0.0);
                m = m * m;
                return 42.0 * dot( m*m, vec4( dot(p0,x0), dot(p1,x1), dot(p2,x2), dot(p3,x3) ) );
              }

              ${shader.vertexShader}
            `;
            
            shader.vertexShader = shader.vertexShader.replace(
                '#include <begin_vertex>',
                `
                #include <begin_vertex>
                
                // Calculate organic distortion
                float noise = snoise(vec3(position.x * 2.0 + uTime, position.y * 2.0 + uTime, position.z * 2.0));
                
                // Add base breathing + audio-reactive distortion
                float distortion = (noise * 0.2) + (noise * uAudio * 0.8);
                
                transformed += normal * distortion;
                `
            );
        };
        
        mesh.material = material;
      }
    })
  }, [scene])

  // Scroll logic
  useEffect(() => {
    if (!group.current) return;
    
    gsap.to(group.current.rotation, {
      y: Math.PI * 2,
      scrollTrigger: {
        trigger: "main",
        start: "top top",
        end: "bottom bottom",
        scrub: 1,
      }
    })
    
    gsap.to(group.current.position, {
      y: -2,
      z: 2,
      scrollTrigger: {
        trigger: "main",
        start: "top top",
        end: "bottom bottom",
        scrub: 1,
      }
    })
  }, [])

  // Floating idle animation, Shader Updates, and Audio Reactivity
  useFrame((state) => {
    if (group.current) {
        group.current.position.y += Math.sin(state.clock.elapsedTime) * 0.002;
        
        // Update shader time for fluid breathing
        uniforms.current.uTime.value = state.clock.elapsedTime * 0.5;

        // Audio reactivity mapping
        let audioTarget = 0;
        let emissiveTarget = 0.5;

        if (isListening) {
            const level = getAudioLevel(); // 0 to 255
            const normalizedLevel = level / 255;
            audioTarget = normalizedLevel;
            emissiveTarget = 0.5 + (normalizedLevel * 4); // Glow intensely when speaking
        }

        // Smoothly interpolate audio uniform for shader distortion
        uniforms.current.uAudio.value = THREE.MathUtils.lerp(uniforms.current.uAudio.value, audioTarget, 0.1);

        // Make it glow based on voice volume
        scene.traverse((child) => {
            if ((child as THREE.Mesh).isMesh) {
                const material = (child as THREE.Mesh).material as THREE.MeshPhysicalMaterial;
                material.emissiveIntensity = THREE.MathUtils.lerp(material.emissiveIntensity, emissiveTarget, 0.1);
            }
        });
    }
  });

  return (
    <group ref={group} {...props} dispose={null}>
      {/* We center the model automatically with primitive */}
      <primitive object={scene} scale={2} position={[0, 0, 0]} />
      <Html position={[0, -2, 0]} center>
          {!isListening ? (
              <button 
                onClick={startListening}
                className="px-4 py-2 bg-indigo-500/10 border border-indigo-500/30 text-indigo-400 text-xs font-mono uppercase tracking-widest rounded-full hover:bg-indigo-500/20 transition-colors pointer-events-auto cursor-pointer whitespace-nowrap"
              >
                  Wake NEXUS
              </button>
          ) : (
              <div className="flex gap-1 items-center px-4 py-2 bg-indigo-500/20 border border-indigo-500/50 rounded-full">
                  <div className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-pulse" />
                  <span className="text-indigo-400 text-xs font-mono uppercase tracking-widest">Listening</span>
              </div>
          )}
      </Html>
    </group>
  )
}

useGLTF.preload('/models/nex.glb')

