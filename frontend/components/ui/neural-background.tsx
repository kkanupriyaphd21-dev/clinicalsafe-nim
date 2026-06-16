"use client";

import { useRef, useMemo } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import * as THREE from "three";

const NODE_COUNT = 60;
const CONNECTION_DISTANCE = 2.2;

function NeuralNetwork() {
  const meshRef = useRef<THREE.Points>(null);
  const linesRef = useRef<THREE.LineSegments>(null);

  const positions = useMemo(() => {
    const pos = new Float32Array(NODE_COUNT * 3);
    for (let i = 0; i < NODE_COUNT; i++) {
      pos[i * 3] = (Math.random() - 0.5) * 12;
      pos[i * 3 + 1] = (Math.random() - 0.5) * 8;
      pos[i * 3 + 2] = (Math.random() - 0.5) * 6;
    }
    return pos;
  }, []);

  const velocities = useMemo(() => {
    const vel = new Float32Array(NODE_COUNT * 3);
    for (let i = 0; i < NODE_COUNT; i++) {
      vel[i * 3] = (Math.random() - 0.5) * 0.004;
      vel[i * 3 + 1] = (Math.random() - 0.5) * 0.004;
      vel[i * 3 + 2] = (Math.random() - 0.5) * 0.004;
    }
    return vel;
  }, []);

  const linePositions = useMemo(
    () => new Float32Array(NODE_COUNT * NODE_COUNT * 6),
    []
  );
  const lineColors = useMemo(
    () => new Float32Array(NODE_COUNT * NODE_COUNT * 6),
    []
  );

  const nodeColors = useMemo(() => {
    const c = new Float32Array(NODE_COUNT * 3);
    const colorA = new THREE.Color("#3B82F6");
    const colorB = new THREE.Color("#1F8A4C");
    for (let i = 0; i < NODE_COUNT; i++) {
      const mixed = colorA.clone().lerp(colorB, Math.random());
      c[i * 3] = mixed.r;
      c[i * 3 + 1] = mixed.g;
      c[i * 3 + 2] = mixed.b;
    }
    return c;
  }, []);

  useFrame(() => {
    if (!meshRef.current || !linesRef.current) return;

    const posAttr = meshRef.current.geometry.attributes.position.array as Float32Array;

    for (let i = 0; i < NODE_COUNT; i++) {
      posAttr[i * 3] += velocities[i * 3];
      posAttr[i * 3 + 1] += velocities[i * 3 + 1];
      posAttr[i * 3 + 2] += velocities[i * 3 + 2];

      if (Math.abs(posAttr[i * 3]) > 6) velocities[i * 3] *= -1;
      if (Math.abs(posAttr[i * 3 + 1]) > 4) velocities[i * 3 + 1] *= -1;
      if (Math.abs(posAttr[i * 3 + 2]) > 3) velocities[i * 3 + 2] *= -1;
    }

    meshRef.current.geometry.attributes.position.needsUpdate = true;

    let lineIdx = 0;
    for (let i = 0; i < NODE_COUNT; i++) {
      for (let j = i + 1; j < NODE_COUNT; j++) {
        const dx = posAttr[i * 3] - posAttr[j * 3];
        const dy = posAttr[i * 3 + 1] - posAttr[j * 3 + 1];
        const dz = posAttr[i * 3 + 2] - posAttr[j * 3 + 2];
        const dist = Math.sqrt(dx * dx + dy * dy + dz * dz);

        if (dist < CONNECTION_DISTANCE) {
          const alpha = 1 - dist / CONNECTION_DISTANCE;
          const base = lineIdx * 6;
          linePositions[base] = posAttr[i * 3];
          linePositions[base + 1] = posAttr[i * 3 + 1];
          linePositions[base + 2] = posAttr[i * 3 + 2];
          linePositions[base + 3] = posAttr[j * 3];
          linePositions[base + 4] = posAttr[j * 3 + 1];
          linePositions[base + 5] = posAttr[j * 3 + 2];

          lineColors[base] = 0.23 * alpha;
          lineColors[base + 1] = 0.51 * alpha;
          lineColors[base + 2] = 0.96 * alpha;
          lineColors[base + 3] = 0.23 * alpha;
          lineColors[base + 4] = 0.51 * alpha;
          lineColors[base + 5] = 0.96 * alpha;
          lineIdx++;
        }
      }
    }

    const geometry = linesRef.current.geometry;
    geometry.setDrawRange(0, lineIdx * 2);
    (geometry.attributes.position.array as Float32Array).set(linePositions);
    (geometry.attributes.color.array as Float32Array).set(lineColors);
    geometry.attributes.position.needsUpdate = true;
    geometry.attributes.color.needsUpdate = true;
  });

  return (
    <>
      <points ref={meshRef}>
        <bufferGeometry>
          <bufferAttribute
            attach="attributes-position"
            args={[positions, 3]}
          />
          <bufferAttribute
            attach="attributes-color"
            args={[nodeColors, 3]}
          />
        </bufferGeometry>
        <pointsMaterial
          size={0.11}
          vertexColors
          transparent
          opacity={1}
          sizeAttenuation
        />
      </points>
      <lineSegments ref={linesRef}>
        <bufferGeometry>
          <bufferAttribute
            attach="attributes-position"
            args={[linePositions, 3]}
          />
          <bufferAttribute
            attach="attributes-color"
            args={[lineColors, 3]}
          />
        </bufferGeometry>
        <lineBasicMaterial vertexColors transparent opacity={0.35} />
      </lineSegments>
    </>
  );
}

export function NeuralBackground() {
  return (
    <div className="pointer-events-none absolute inset-0 -z-10 overflow-hidden">
      <Canvas
        camera={{ position: [0, 0, 7], fov: 60 }}
        gl={{ antialias: true, alpha: true }}
        dpr={[1, 1.5]}
      >
        <ambientLight intensity={0.6} />
        <NeuralNetwork />
      </Canvas>
      <div className="absolute inset-0 bg-gradient-to-b from-clinical/5 via-clinical/15 to-clinical/70" />
    </div>
  );
}
