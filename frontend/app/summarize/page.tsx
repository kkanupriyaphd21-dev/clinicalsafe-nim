"use client";

import { useEffect, useState, Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea, Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Alert } from "@/components/ui/alert";
import { ProgressBar } from "@/components/ui/progress-bar";
import { NeuralBackground } from "@/components/ui/neural-background";
import { api, SummarizeResponse, CSRProgress } from "@/lib/api";
import {
  ArrowLeft,
  Send,
  FileUp,
  Download,
  Loader2,
  CheckCircle,
  AlertTriangle,
  Sparkles,
  FileText,
  Table2,
  Clock,
  Zap,
} from "lucide-react";

const DEFAULT_MODEL = "meta/llama-3.3-70b-instruct";
const SAMPLE_TABLE = `start_table [TABLE_TITLE: Table 1: Adverse Events]
[HEADERS: | Placebo N=100 | Drug N=100]
[ROW] Any TEAE | 80 (80.0%) | 75 (75.0%)
[ROW] Grade 3-4 AE | 10 (10.0%) | 12 (12.0%)
[ROW] Serious AE | 5 (5.0%) | 4 (4.0%)
[ROW] Discontinuation | 3 (3.0%) | 2 (2.0%)
end_table`;

function SummarizeContent() {
  const searchParams = useSearchParams();
  const [activeTab, setActiveTab] = useState<"table" | "csr">(
    searchParams.get("tab") === "csr" ? "csr" : "table"
  );
  const [tableText, setTableText] = useState(SAMPLE_TABLE);
  const [model, setModel] = useState(DEFAULT_MODEL);
  const [result, setResult] = useState<SummarizeResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [csrFile, setCsrFile] = useState<File | null>(null);
  const [csrTaskId, setCsrTaskId] = useState<string | null>(null);
  const [csrProgress, setCsrProgress] = useState<CSRProgress | null>(null);
  const [csrResult, setCsrResult] = useState<Record<string, unknown> | null>(null);
  const [csrProcessing, setCsrProcessing] = useState(false);

  const handleSummarize = async () => {
    if (!tableText.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await api.summarize({ table_text: tableText, model });
      setResult(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Summarization failed");
    } finally {
      setLoading(false);
    }
  };

  const handleCSRUpload = async () => {
    if (!csrFile) {
      setError("Please select a PDF file first.");
      return;
    }
    setCsrProcessing(true);
    setError(null);
    setCsrResult(null);
    setCsrProgress(null);
    setCsrTaskId(null);
    try {
      const data = await api.startCSR(csrFile, { model });
      setCsrTaskId(data.task_id);
      pollCSR(data.task_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "CSR upload failed");
      setCsrProcessing(false);
    }
  };

  const pollCSR = (taskId: string) => {
    let stopped = false;
    const doPoll = async () => {
      if (stopped) return;
      try {
        const prog = await api.getCSRProgress(taskId);
        if (stopped) return;
        setCsrProgress(prog);
        if (prog.status === "complete" && prog.result) {
          setCsrResult(prog.result);
          setCsrProcessing(false);
          return;
        }
        if (prog.status === "error") {
          setError(prog.error || "CSR processing failed");
          setCsrProcessing(false);
          return;
        }
        setTimeout(doPoll, 2000);
      } catch (e) {
        if (stopped) return;
        setError(e instanceof Error ? e.message : "Progress poll failed");
        setCsrProcessing(false);
      }
    };
    setTimeout(doPoll, 1000);
  };

  const downloadCSRFile = async (
    fetchFn: (token: string) => Promise<Response>,
    filename: string
  ) => {
    const token = csrResult?.download_token as string;
    if (!token) return;
    try {
      const res = await fetchFn(token);
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error((data as { detail?: string }).detail || res.statusText);
      }
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Download failed");
    }
  };

  const TabButton = ({
    id,
    label,
    icon: Icon,
  }: {
    id: "table" | "csr";
    label: string;
    icon: React.ComponentType<{ className?: string }>;
  }) => (
    <button
      onClick={() => setActiveTab(id)}
      className={`flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium transition-all ${
        activeTab === id
          ? "bg-accent text-white shadow-lg shadow-accent/25"
          : "bg-white/5 text-cortex hover:bg-white/10 hover:text-parchment"
      }`}
    >
      <Icon className="h-4 w-4" />
      {label}
    </button>
  );

  return (
    <main className="relative min-h-screen overflow-hidden bg-clinical">
      <NeuralBackground />

      <header className="relative border-b border-white/5 bg-ink/40 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-4">
            <Link href="/">
              <Button variant="ghost" size="sm" className="text-cortex hover:text-parchment">
                <ArrowLeft className="mr-2 h-4 w-4" /> Back
              </Button>
            </Link>
            <h1 className="text-xl font-bold text-parchment">Summarizer</h1>
          </div>
          <div className="flex gap-2">
            <TabButton id="table" label="Single Table" icon={Table2} />
            <TabButton id="csr" label="CSR PDF" icon={FileText} />
          </div>
        </div>
      </header>

      <div className="relative mx-auto max-w-7xl px-6 py-10">
        <AnimatePresence mode="wait">
          {error && (
            <motion.div
              key="error"
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
            >
              <Alert variant="error" className="mb-6">
                {error}
              </Alert>
            </motion.div>
          )}
        </AnimatePresence>

        {activeTab === "table" ? (
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.4 }}
            className="grid gap-8 lg:grid-cols-2"
          >
            <Card className="glass-card">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-xl">
                  <Table2 className="h-5 w-5 text-accent" />
                  Clinical Safety Table
                </CardTitle>
                <CardDescription>
                  Paste a linearized table or edit the sample below.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-5">
                <div>
                  <label className="mb-1.5 block text-sm font-medium text-cortex">Model</label>
                  <Input
                    value={model}
                    onChange={(e) => setModel(e.target.value)}
                    placeholder={DEFAULT_MODEL}
                    className="bg-ink/50"
                  />
                </div>
                <div>
                  <label className="mb-1.5 block text-sm font-medium text-cortex">Table text</label>
                  <Textarea
                    value={tableText}
                    onChange={(e) => setTableText(e.target.value)}
                    className="min-h-[340px] bg-ink/50 font-mono text-sm"
                  />
                </div>
                <Button
                  onClick={handleSummarize}
                  isLoading={loading}
                  className="w-full bg-gradient-to-r from-accent to-blue-600 hover:from-blue-500 hover:to-blue-700"
                >
                  <Send className="mr-2 h-4 w-4" /> Summarize with NIM
                </Button>
              </CardContent>
            </Card>

            <div className="space-y-6">
              {result ? (
                <motion.div
                  initial={{ opacity: 0, scale: 0.98 }}
                  animate={{ opacity: 1, scale: 1 }}
                >
                  <Card className="glass-card">
                    <CardHeader>
                      <div className="flex items-center justify-between">
                        <CardTitle className="flex items-center gap-2 text-xl">
                          <Sparkles className="h-5 w-5 text-accent" />
                          NIM Summary
                        </CardTitle>
                        <div className="flex gap-2">
                          {result.verified ? (
                            <Badge variant="success" className="px-2.5 py-1">
                              <CheckCircle className="mr-1 h-3 w-3" /> Verified
                            </Badge>
                          ) : (
                            <Badge variant="warning" className="px-2.5 py-1">
                              <AlertTriangle className="mr-1 h-3 w-3" /> Review
                            </Badge>
                          )}
                          <Badge variant="info" className="px-2.5 py-1">
                            {Math.round(result.numeric_accuracy * 100)}% accuracy
                          </Badge>
                        </div>
                      </div>
                      <CardDescription>
                        {result.model_used} • {result.inference_time_ms}ms
                        {result.tokens_generated !== null && ` • ${result.tokens_generated} tokens`}
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-5">
                      <div className="rounded-xl border border-white/5 bg-ink/70 p-5 text-sm leading-relaxed text-parchment shadow-inner">
                        {result.summary}
                      </div>
                      {result.warnings.length > 0 && (
                        <div className="space-y-2">
                          {result.warnings.map((w, i) => (
                            <Alert key={i} variant="warning">
                              {w}
                            </Alert>
                          ))}
                        </div>
                      )}
                      {result.extracted_facts.length > 0 && (
                        <div>
                          <h4 className="mb-3 text-sm font-medium text-parchment">
                            Provenance ({result.extracted_facts.filter((f) => f.status === "verified").length}{" "}
                            verified)
                          </h4>
                          <div className="max-h-60 overflow-auto rounded-xl border border-white/5">
                            <table className="w-full text-left text-xs">
                              <thead className="bg-white/5 text-parchment">
                                <tr>
                                  <th className="px-3 py-2">Value</th>
                                  <th className="px-3 py-2">Source</th>
                                  <th className="px-3 py-2">Status</th>
                                </tr>
                              </thead>
                              <tbody>
                                {result.extracted_facts.slice(0, 50).map((f, i) => (
                                  <tr key={i} className="border-t border-white/5">
                                    <td className="px-3 py-2 font-mono text-parchment">{String(f.value)}</td>
                                    <td className="px-3 py-2 text-cortex">
                                      {String(f.source_label || "—")} = {String(f.source_value_repr || "—")}
                                    </td>
                                    <td className="px-3 py-2">
                                      <Badge variant={f.status === "verified" ? "success" : "warning"}>
                                        {String(f.status)}
                                      </Badge>
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                </motion.div>
              ) : (
                <Card className="flex h-full min-h-[320px] flex-col items-center justify-center glass-card text-center">
                  <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-white/5">
                    <Sparkles className="h-8 w-8 text-cortex" />
                  </div>
                  <p className="text-cortex">Run summarization to see verified results here.</p>
                </Card>
              )}
            </div>
          </motion.div>
        ) : (
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.4 }}
            className="grid gap-8 lg:grid-cols-2"
          >
            <Card className="glass-card">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-xl">
                  <FileText className="h-5 w-5 text-accent" />
                  CSR PDF Pipeline
                </CardTitle>
                <CardDescription>
                  Upload a full Clinical Study Report PDF. The pipeline extracts sections and tables,
                  summarizes each table, and produces a structured DOCX.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-5">
                <div>
                  <label className="mb-1.5 block text-sm font-medium text-cortex">Model</label>
                  <Input value={model} onChange={(e) => setModel(e.target.value)} className="bg-ink/50" />
                </div>
                <div>
                  <label className="mb-1.5 block text-sm font-medium text-cortex">PDF file</label>
                  <input
                    type="file"
                    accept=".pdf,application/pdf"
                    onChange={(e) => setCsrFile(e.target.files?.[0] || null)}
                    className="block w-full rounded-xl border border-white/10 bg-ink/50 px-4 py-3 text-sm text-parchment file:mr-4 file:rounded-lg file:border-0 file:bg-accent file:px-4 file:py-2 file:text-white file:transition-colors hover:file:bg-blue-500"
                  />
                </div>
                <Button
                  onClick={handleCSRUpload}
                  isLoading={csrProcessing && !csrTaskId}
                  disabled={!csrFile || csrProcessing}
                  className="w-full bg-gradient-to-r from-accent to-blue-600 hover:from-blue-500 hover:to-blue-700"
                >
                  <FileUp className="mr-2 h-4 w-4" /> Start CSR Pipeline
                </Button>
              </CardContent>
            </Card>

            <Card className="glass-card">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-xl">
                  <Clock className="h-5 w-5 text-accent" />
                  Progress
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-5">
                {!csrProgress && !csrResult && (
                  <div className="flex h-48 flex-col items-center justify-center text-center">
                    <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-white/5">
                      <FileText className="h-7 w-7 text-cortex" />
                    </div>
                    <p className="text-cortex">Upload a PDF to begin processing.</p>
                  </div>
                )}
                {csrProgress && (
                  <>
                    <div className="flex items-center justify-between text-sm">
                      <span className="capitalize text-parchment">{csrProgress.stage}</span>
                      <span className="text-cortex">
                        {csrProgress.current}/{csrProgress.total}
                      </span>
                    </div>
                    <ProgressBar value={csrProgress.progress} />
                    <p className="text-sm text-cortex">{csrProgress.message}</p>
                    <p className="text-xs text-cortex">
                      Elapsed: {csrProgress.elapsed_seconds}s • ETA: {csrProgress.eta_seconds}s
                    </p>
                  </>
                )}
                {csrResult && (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="space-y-5"
                  >
                    <div className="grid grid-cols-2 gap-4">
                      <div className="rounded-xl border border-white/5 bg-ink/50 p-4">
                        <p className="text-xs text-cortex">Sections</p>
                        <p className="text-2xl font-bold text-parchment">
                          {Array.isArray(csrResult.sections) ? csrResult.sections.length : 0}
                        </p>
                      </div>
                      <div className="rounded-xl border border-white/5 bg-ink/50 p-4">
                        <p className="text-xs text-cortex">Tables</p>
                        <p className="text-2xl font-bold text-parchment">{String(csrResult.total_tables)}</p>
                      </div>
                      <div className="rounded-xl border border-white/5 bg-ink/50 p-4">
                        <p className="text-xs text-cortex">Verified</p>
                        <p className="text-2xl font-bold text-verified">{String(csrResult.verified_tables)}</p>
                      </div>
                      <div className="rounded-xl border border-white/5 bg-ink/50 p-4">
                        <p className="text-xs text-cortex">Accuracy</p>
                        <p className="text-2xl font-bold text-accent">
                          {Math.round(Number(csrResult.overall_numeric_accuracy) * 100)}%
                        </p>
                      </div>
                    </div>
                    <div className="grid gap-3">
                      <Button
                        onClick={() => downloadCSRFile(api.downloadCSRDocx, `csr-nim-${Date.now()}.docx`)}
                        className="w-full bg-gradient-to-r from-verified to-emerald-600 hover:from-emerald-500 hover:to-emerald-700"
                      >
                        <Download className="mr-2 h-4 w-4" /> Download Deliverable DOCX
                      </Button>
                      <div className="grid grid-cols-2 gap-3">
                        <Button
                          variant="outline"
                          onClick={() => downloadCSRFile(api.downloadCSRQcReport, `csr-nim-qc-${Date.now()}.docx`)}
                          className="w-full border-white/10 bg-white/5 hover:border-accent/50 hover:bg-accent hover:text-white"
                        >
                          <Download className="mr-2 h-4 w-4" /> QC Report
                        </Button>
                        <Button
                          variant="outline"
                          onClick={() => downloadCSRFile(api.downloadCSRAuditLog, `csr-nim-audit-${Date.now()}.json`)}
                          className="w-full border-white/10 bg-white/5 hover:border-accent/50 hover:bg-accent hover:text-white"
                        >
                          <Download className="mr-2 h-4 w-4" /> Audit JSON
                        </Button>
                      </div>
                    </div>
                  </motion.div>
                )}
              </CardContent>
            </Card>
          </motion.div>
        )}
      </div>
    </main>
  );
}

export default function SummarizePage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-clinical" />}>
      <SummarizeContent />
    </Suspense>
  );
}
