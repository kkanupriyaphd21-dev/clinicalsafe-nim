"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api, HealthResponse } from "@/lib/api";
import { FileText, ArrowRight, Shield, CheckCircle, Eye } from "lucide-react";

function BackgroundGrid() {
  return (
    <div className="pointer-events-none fixed inset-0 -z-10">
      <div className="absolute inset-0 bg-[linear-gradient(rgba(59,130,246,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(59,130,246,0.03)_1px,transparent_1px)] bg-[size:56px_56px]" />
      <div className="absolute inset-0 bg-gradient-to-b from-clinical/0 via-clinical/50 to-clinical" />
      <div className="absolute left-1/2 top-0 h-[600px] w-[800px] -translate-x-1/2 rounded-full bg-accent/5 blur-[120px]" />
    </div>
  );
}

const container = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.12 },
  },
};

const item = {
  hidden: { opacity: 0, y: 24 },
  show: { opacity: 1, y: 0, transition: { duration: 0.6, ease: [0.25, 0.1, 0.25, 1] } },
};

export default function DashboardPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.health()
      .then(setHealth)
      .catch((e) => setError(e.message));
  }, []);

  const features = [
    {
      title: "Single-Table Summarizer",
      description: "Submit clinical safety tables to NVIDIA NIM and receive verified narrative summaries with source-grounded numeric validation.",
      icon: FileText,
      href: "/summarize",
    },
  ];

  return (
    <main className="relative min-h-screen overflow-hidden bg-clinical">
      <BackgroundGrid />

      <motion.div
        variants={container}
        initial="hidden"
        animate="show"
        className="mx-auto flex min-h-screen max-w-5xl flex-col px-6"
      >
        {/* Header */}
        <motion.header variants={item} className="flex items-center justify-between py-6">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-accent to-teal shadow-lg shadow-accent/20">
              <Shield className="h-5 w-5 text-white" />
            </div>
            <div>
              <h1 className="text-lg font-semibold text-parchment tracking-tight">ClinicalSafe NIM</h1>
              <p className="text-xs text-cortex/70">Clinical summarization platform</p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            {health ? (
              <div className="flex items-center gap-2">
                <span className="text-xs text-cortex/60">{health.version}</span>
                <Badge variant="success" className="px-3 py-0.5 text-[11px] uppercase tracking-wider">
                  {health.status}
                </Badge>
              </div>
            ) : (
              <Badge variant="warning" className="text-[11px] uppercase tracking-wider">
                {error ? "Offline" : "Connecting…"}
              </Badge>
            )}
          </div>
        </motion.header>

        {/* Hero */}
        <motion.section variants={item} className="mt-16 mb-20 text-center">
          <Badge className="mb-6 border-white/10 bg-white/[0.04] px-4 py-1.5 text-[11px] uppercase tracking-[0.15em] text-cortex/80">
            Powered by NVIDIA NIM
          </Badge>
          <h2 className="mx-auto max-w-3xl text-5xl font-light leading-[1.1] tracking-tight text-parchment sm:text-6xl">
            Turn clinical tables into{" "}
            <span className="font-semibold text-accent">narrative summaries</span>
          </h2>
          <p className="mx-auto mt-6 max-w-xl text-base leading-relaxed text-cortex/70">
            A premium clinical summarization engine that transforms safety tables
            into hallucination-guarded, verifiable narratives — with no API key management to burden your team.
          </p>
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.4, duration: 0.6 }}
            className="mt-10 flex items-center justify-center gap-2 text-xs text-cortex/50"
          >
            <CheckCircle className="h-3.5 w-3.5 text-verified" />
            <span>Numeric verification on every output</span>
            <span className="mx-2">·</span>
            <Eye className="h-3.5 w-3.5 text-accent/60" />
            <span>Zero hallucination tolerance</span>
          </motion.div>
        </motion.section>

        {/* Feature cards */}
        <motion.div variants={item} className="mx-auto max-w-md">
          {features.map((feature) => (
            <Card
              key={feature.title}
              className="group relative border-white/[0.06] bg-white/[0.02] transition-all duration-500 hover:border-white/10 hover:bg-white/[0.04] hover:shadow-[0_0_40px_-12px_rgba(59,130,246,0.2)]"
            >
              <CardHeader>
                <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-white/[0.04] transition-all duration-300 group-hover:bg-accent/10 group-hover:shadow-[0_0_20px_-4px_rgba(59,130,246,0.15)]">
                  <feature.icon className="h-5 w-5 text-accent/70 transition-colors duration-300 group-hover:text-accent" />
                </div>
                <CardTitle className="text-lg font-medium tracking-tight">{feature.title}</CardTitle>
                <CardDescription className="text-sm leading-relaxed text-cortex/60">
                  {feature.description}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Link href={feature.href}>
                  <Button
                    variant="outline"
                    className="w-full border-white/[0.08] bg-white/[0.02] text-sm text-cortex/70 transition-all duration-300 hover:border-accent/30 hover:bg-accent/10 hover:text-accent"
                  >
                    Launch <ArrowRight className="ml-2 h-3.5 w-3.5 transition-transform duration-300 group-hover:translate-x-1" />
                  </Button>
                </Link>
              </CardContent>
            </Card>
          ))}
        </motion.div>

        {/* Footer */}
        <motion.div variants={item} className="mt-auto py-10 text-center">
          <p className="text-[11px] uppercase tracking-[0.2em] text-cortex/30">
            ClinicalSafe NIM · NVIDIA NIM backend
          </p>
        </motion.div>
      </motion.div>
    </main>
  );
}
