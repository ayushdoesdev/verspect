"use client";

import { Canvas, useFrame } from "@react-three/fiber";
import { Float } from "@react-three/drei";
import { useMemo, useRef } from "react";
import * as THREE from "three";

function OrbitingNodes() {
  const group = useRef<THREE.Group>(null);
  const nodes = useMemo(
    () =>
      Array.from({ length: 18 }).map((_, i) => ({
        position: [
          Math.cos((i / 18) * Math.PI * 2) * (1.4 + (i % 3) * 0.25),
          (i % 5) * 0.18 - 0.4,
          Math.sin((i / 18) * Math.PI * 2) * (1.4 + (i % 3) * 0.25),
        ] as [number, number, number],
        scale: 0.04 + (i % 4) * 0.015,
      })),
    [],
  );

  useFrame((_, delta) => {
    if (group.current) group.current.rotation.y += delta * 0.25;
  });

  return (
    <group ref={group}>
      <mesh>
        <torusGeometry args={[1.6, 0.01, 16, 100]} />
        <meshBasicMaterial color="#3dd6c6" transparent opacity={0.35} />
      </mesh>
      <mesh rotation={[Math.PI / 2.4, 0.2, 0]}>
        <torusGeometry args={[1.15, 0.008, 16, 100]} />
        <meshBasicMaterial color="#6c9eff" transparent opacity={0.3} />
      </mesh>
      {nodes.map((n, i) => (
        <Float key={i} speed={1.5 + (i % 3)} floatIntensity={0.4}>
          <mesh position={n.position}>
            <sphereGeometry args={[n.scale, 16, 16]} />
            <meshStandardMaterial
              color={i % 3 === 0 ? "#3dd6c6" : i % 3 === 1 ? "#6c9eff" : "#e6b450"}
              emissive={i % 3 === 0 ? "#0d9488" : "#1e3a8a"}
              emissiveIntensity={0.4}
            />
          </mesh>
        </Float>
      ))}
      <mesh>
        <icosahedronGeometry args={[0.35, 1]} />
        <meshStandardMaterial color="#3dd6c6" wireframe transparent opacity={0.55} />
      </mesh>
    </group>
  );
}

export function ScanVisualization() {
  return (
    <div className="relative h-[340px] w-full overflow-hidden rounded-2xl border border-white/10 bg-gradient-to-b from-[#0c1522] to-[#070b12] shadow-[0_0_80px_rgba(61,214,198,0.12)] sm:h-[420px]">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(61,214,198,0.12),transparent_60%)]" />
      <Canvas camera={{ position: [0, 0.6, 4.2], fov: 42 }}>
        <ambientLight intensity={0.55} />
        <pointLight position={[4, 4, 4]} intensity={1.2} color="#3dd6c6" />
        <pointLight position={[-4, -2, 2]} intensity={0.6} color="#6c9eff" />
        <OrbitingNodes />
      </Canvas>
      <div className="pointer-events-none absolute bottom-4 left-4 right-4 flex items-center justify-between text-[11px] text-slate-400">
        <span className="rounded-full border border-white/10 bg-black/40 px-3 py-1 backdrop-blur">
          Scanning repository graph…
        </span>
        <span className="font-mono text-teal-300/80">AST · CVE · MIGRATE</span>
      </div>
    </div>
  );
}
