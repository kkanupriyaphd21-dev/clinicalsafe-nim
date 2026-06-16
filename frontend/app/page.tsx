"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api, HealthResponse } from "@/lib/api";
import { useRouter } from "next/navigation";
import { 
  FileText, 
  ArrowRight, 
  Shield, 
  CheckCircle, 
  Eye, 
  KeyRound, 
  Layers, 
  Database,
  Activity,
  Cpu,
  FileCheck,
  User,
  LogOut
} from "lucide-react";

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
    transition: { staggerChildren: 0.1 },
  },
};

const item = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.5, ease: [0.25, 0.1, 0.25, 1] } },
};

export default function DashboardPage() {
  const router = useRouter();
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [username, setUsername] = useState<string | null>(null);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      router.push("/login");
      return;
    }
    setUsername(localStorage.getItem("username") || "User");

    api.health()
      .then(setHealth)
      .catch((e) => setError(e.message));
  }, [router]);

  const features = [
    {
      title: "CSR PDF Pipeline",
      description: "Upload a complete Clinical Study Report PDF. Automatically detects sections, extracts and classifies tables, generates parallel NIM summaries, checks cross-table consistency, and compiles structured Word documents.",
      icon: Layers,
      badge: "Pipeline",
      color: "from-teal-500/10 to-emerald-500/10 border-teal-500/20 hover:border-teal-500/50",
      iconColor: "text-teal-400",
      buttonColor: "hover:bg-teal-500/10 hover:text-teal-400 hover:border-teal-500/30",
      href: "/summarize?tab=csr",
    },
    {
      title: "Single-Table Summarizer",
      description: "Submit individual clinical safety tables in linearized format. Receives regulatory-grade narrative summaries from NVIDIA NIM with exact numeric accuracy verification and source-grounded fact-checking.",
      icon: FileText,
      badge: "Quick Tool",
      color: "from-blue-500/10 to-indigo-500/10 border-blue-500/20 hover:border-blue-500/50",
      iconColor: "text-blue-400",
      buttonColor: "hover:bg-blue-500/10 hover:text-blue-400 hover:border-blue-500/30",
      href: "/summarize?tab=table",
    },
    {
      title: "API Key Vault",
      description: "Secure, encrypted key storage for NVIDIA NIM API keys. Configured with AES-256 Fernet encryption at rest, real-time usage and token statistics tracking, and auto-rotation on HTTP 401/402/429 errors.",
      icon: KeyRound,
      badge: "Security",
      color: "from-purple-500/10 to-pink-500/10 border-purple-500/20 hover:border-purple-500/50",
      iconColor: "text-purple-400",
      buttonColor: "hover:bg-purple-500/10 hover:text-purple-400 hover:border-purple-500/30",
      href: "/keys",
    },
  ];

  return (
    <main className="relative min-h-screen overflow-hidden bg-clinical">
      <BackgroundGrid />

      <motion.div
        variants={container}
        initial="hidden"
        animate="show"
        className="mx-auto flex min-h-screen max-w-6xl flex-col px-6 py-6"
      >
        {/* Header */}
        <motion.header variants={item} className="flex flex-col gap-4 border-b border-white/5 pb-6 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-accent to-teal shadow-lg shadow-accent/20">
              <Shield className="h-5.5 w-5.5 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-parchment tracking-tight">ClinicalSafe NIM</h1>
              <p className="text-xs text-cortex/70">Secure NVIDIA NIM Clinical Narrative & QC Orchestrator</p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            {username && (
              <div className="flex items-center gap-2 rounded-lg border border-white/5 bg-white/[0.02] px-3 py-1.5 text-xs">
                <User className="h-3.5 w-3.5 text-cortex" />
                <span className="text-cortex">{username}</span>
              </div>
            )}
            {health ? (
              <div className="flex items-center gap-3">
                <span className="hidden text-xs text-cortex/60 sm:inline">Engine: {health.default_model.split("/").pop()}</span>
                <Badge variant="success" className="px-3 py-1 text-[10px] font-semibold uppercase tracking-wider">
                  System {health.status}
                </Badge>
              </div>
            ) : (
              <Badge variant="warning" className="px-3 py-1 text-[10px] font-semibold uppercase tracking-wider">
                {error ? "Offline" : "Checking Connection…"}
              </Badge>
            )}
            {username && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  localStorage.removeItem("token");
                  localStorage.removeItem("username");
                  router.push("/login");
                }}
                className="h-8 border-red-500/20 text-red-400 hover:bg-red-500/10 hover:text-red-300 transition-colors"
              >
                <LogOut className="mr-1.5 h-3.5 w-3.5" />
                Sign Out
              </Button>
            )}
          </div>
        </motion.header>

        {/* Hero Section */}
        <motion.section variants={item} className="mt-12 mb-12 text-center">
          <Badge className="mb-6 border-white/10 bg-white/[0.04] px-4 py-1.5 text-[11px] uppercase tracking-[0.15em] text-cortex/80">
            NVIDIA NIM Clinical Intelligence
          </Badge>
          <h2 className="mx-auto max-w-4xl text-4xl font-light leading-[1.15] tracking-tight text-parchment sm:text-5xl md:text-6xl">
            Automated, Verified summaries for <br />
            <span className="font-semibold text-accent gradient-text">Clinical study reports</span>
          </h2>
          <p className="mx-auto mt-6 max-w-2xl text-base leading-relaxed text-cortex/70">
            A premium clinical narrative synthesis system. Transforms raw tables into 
            hallucination-guarded ICH E3 compliant text with mathematical verification, 
            consistency checks, and secure API rotation.
          </p>
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.3, duration: 0.6 }}
            className="mt-8 flex flex-wrap items-center justify-center gap-6 text-xs text-cortex/60"
          >
            <div className="flex items-center gap-1.5">
              <CheckCircle className="h-4 w-4 text-verified" />
              <span>&ge;95% Numeric Accuracy Verified</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Eye className="h-4 w-4 text-accent" />
              <span>Fact-to-Cell Provenance Mapping</span>
            </div>
            <div className="flex items-center gap-1.5">
              <FileCheck className="h-4 w-4 text-teal-400" />
              <span>21 CFR Part 11 Audit Trail compliant</span>
            </div>
          </motion.div>
        </motion.section>

        {/* Stats Widget Row */}
        {health && (
          <motion.div variants={item} className="mb-10 grid grid-cols-2 gap-4 rounded-2xl border border-white/5 bg-white/[0.01] p-4 backdrop-blur-md sm:grid-cols-4">
            <div className="flex items-center gap-3 px-3 py-2">
              <Database className="h-8 w-8 text-accent/50" />
              <div>
                <p className="text-[10px] uppercase tracking-wider text-cortex/60">Vault Keys</p>
                <p className="text-lg font-bold text-parchment">{health.total_keys} stored</p>
              </div>
            </div>
            <div className="flex items-center gap-3 px-3 py-2">
              <Activity className="h-8 w-8 text-verified/50" />
              <div>
                <p className="text-[10px] uppercase tracking-wider text-cortex/60">Active Keys</p>
                <p className="text-lg font-bold text-verified">{health.active_keys} ready</p>
              </div>
            </div>
            <div className="flex items-center gap-3 px-3 py-2">
              <Cpu className="h-8 w-8 text-teal-400/50" />
              <div>
                <p className="text-[10px] uppercase tracking-wider text-cortex/60">NIM Engine</p>
                <p className="truncate text-sm font-semibold text-parchment">Llama-3.3-70b</p>
              </div>
            </div>
            <div className="flex items-center gap-3 px-3 py-2">
              <CheckCircle className="h-8 w-8 text-purple-400/50" />
              <div>
                <p className="text-[10px] uppercase tracking-wider text-cortex/60">Encryption</p>
                <p className="text-sm font-semibold text-parchment">AES-256 Fernet</p>
              </div>
            </div>
          </motion.div>
        )}

        {/* Feature Grid */}
        <motion.div variants={item} className="grid gap-6 md:grid-cols-3">
          {features.map((feature, idx) => (
            <Card
              key={feature.title}
              className={`relative flex flex-col justify-between overflow-hidden border bg-gradient-to-b ${feature.color} p-2 transition-all duration-500 hover:shadow-[0_0_50px_-12px_rgba(59,130,246,0.15)]`}
            >
              <CardHeader className="pb-4">
                <div className="flex items-center justify-between">
                  <div className={`flex h-12 w-12 items-center justify-center rounded-xl bg-white/[0.03] transition-all duration-300`}>
                    <feature.icon className={`h-6 w-6 ${feature.iconColor}`} />
                  </div>
                  <Badge variant="default" className="border border-white/10 bg-white/5 text-[9px] uppercase tracking-wider text-cortex">
                    {feature.badge}
                  </Badge>
                </div>
                <CardTitle className="mt-4 text-xl font-semibold tracking-tight text-parchment">{feature.title}</CardTitle>
                <CardDescription className="mt-2 text-sm leading-relaxed text-cortex/70">
                  {feature.description}
                </CardDescription>
              </CardHeader>
              <CardContent className="pt-2">
                <Link href={feature.href}>
                  <Button
                    variant="outline"
                    className={`w-full border-white/[0.08] bg-white/[0.02] text-sm text-cortex/80 transition-all duration-300 ${feature.buttonColor}`}
                  >
                    Launch Module <ArrowRight className="ml-2 h-4 w-4" />
                  </Button>
                </Link>
              </CardContent>
            </Card>
          ))}
        </motion.div>

        {/* Security & Audits Banner */}
        <motion.div variants={item} className="mt-12 rounded-2xl border border-white/5 bg-white/[0.02] p-6 text-left backdrop-blur-md">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-blue-500/10">
              <Shield className="h-5 w-5 text-accent" />
            </div>
            <div>
              <h4 className="text-sm font-semibold text-parchment">Regulatory Compliance & Vault Auditing</h4>
              <p className="mt-1 text-xs leading-relaxed text-cortex/70">
                All NIM API keys are encrypted at rest with cryptography Fernet. In compliance with <strong>21 CFR Part 11</strong>, 
                every LLM generation is mathematically evaluated for numerical correctness against raw study sources, 
                and all activities are captured in detailed log audits and QC reports.
              </p>
            </div>
          </div>
        </motion.div>

        {/* Footer */}
        <motion.div variants={item} className="mt-auto pt-16 pb-8 text-center">
          <p className="text-[10px] uppercase tracking-[0.25em] text-cortex/30">
            ClinicalSafe NIM &middot; Production Release v1.0.0 &middot; Secure Sandbox
          </p>
        </motion.div>
      </motion.div>
    </main>
  );
}
