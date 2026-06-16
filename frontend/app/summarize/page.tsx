"use client";

import { useEffect, useState, Suspense } from "react";
import Link from "next/link";
import { useSearchParams, useRouter } from "next/navigation";
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
  ChevronDown,
  ChevronUp,
  Info,
  XCircle,
  ShieldAlert,
  ArrowRight,
  Database,
  ExternalLink
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
  const router = useRouter();
  const searchParams = useSearchParams();

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      router.push("/login");
    }
  }, [router]);

  const [activeTab, setActiveTab] = useState<"table" | "csr">(
    searchParams.get("tab") === "csr" ? "csr" : "table"
  );
  const [tableText, setTableText] = useState(SAMPLE_TABLE);
  const [model, setModel] = useState(DEFAULT_MODEL);
  const [result, setResult] = useState<SummarizeResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // CSR PDF States
  const [csrFile, setCsrFile] = useState<File | null>(null);
  const [csrTaskId, setCsrTaskId] = useState<string | null>(null);
  const [csrProgress, setCsrProgress] = useState<CSRProgress | null>(null);
  const [csrResult, setCsrResult] = useState<Record<string, any> | null>(null);
  const [csrProcessing, setCsrProcessing] = useState(false);

  // Interactive Workspace States
  const [activeResultTab, setActiveResultTab] = useState<"synthesis" | "quality" | "sections">("synthesis");
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({});
  const [expandedTables, setExpandedTables] = useState<Record<string, boolean>>({});

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
    const doPoll = async () => {
      try {
        const prog = await api.getCSRProgress(taskId);
        setCsrProgress(prog);
        if (prog.status === "complete" && prog.result) {
          const resultData = prog.result as any;
          setCsrResult(resultData);
          setCsrProcessing(false);
          // Initialize first section expanded
          if (resultData.sections && resultData.sections.length > 0) {
            setExpandedSections({ [resultData.sections[0].section_number]: true });
          }
          return;
        }
        if (prog.status === "error") {
          setError(prog.error || "CSR processing failed");
          setCsrProcessing(false);
          return;
        }
        setTimeout(doPoll, 2000);
      } catch (e) {
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

  const toggleSection = (sectionNumber: string) => {
    setExpandedSections(prev => ({
      ...prev,
      [sectionNumber]: !prev[sectionNumber]
    }));
  };

  const toggleTable = (tableId: string) => {
    setExpandedTables(prev => ({
      ...prev,
      [tableId]: !prev[tableId]
    }));
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
      onClick={() => {
        setActiveTab(id);
        setError(null);
      }}
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
            <h1 className="text-xl font-bold text-parchment">Clinical Narrative Engine</h1>
          </div>
          <div className="flex gap-2">
            <TabButton id="table" label="Single Table" icon={Table2} />
            <TabButton id="csr" label="CSR PDF Pipeline" icon={FileText} />
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
                  Paste a linearized table or edit the sample below. Use pipes to separate headers and cell values.
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
                  className="w-full bg-gradient-to-r from-accent to-blue-600 hover:from-blue-500 hover:to-blue-700 font-semibold"
                >
                  <Send className="mr-2 h-4 w-4" /> Summarize Table with NIM
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
                      <div className="flex flex-wrap items-center justify-between gap-4">
                        <div>
                          <CardTitle className="flex items-center gap-2 text-xl text-parchment">
                            <Sparkles className="h-5 w-5 text-accent" />
                            NIM Generated Summary
                          </CardTitle>
                          <CardDescription>
                            {result.model_used} &bull; {result.inference_time_ms}ms
                            {result.tokens_generated !== null && ` &bull; ${result.tokens_generated} tokens`}
                          </CardDescription>
                        </div>
                        <div className="flex gap-2">
                          {result.verified ? (
                            <Badge variant="success" className="px-2.5 py-1 text-xs">
                              <CheckCircle className="mr-1 h-3 w-3" /> Verified
                            </Badge>
                          ) : (
                            <Badge variant="warning" className="px-2.5 py-1 text-xs">
                              <AlertTriangle className="mr-1 h-3 w-3" /> Audit Review
                            </Badge>
                          )}
                          <Badge variant="info" className="px-2.5 py-1 text-xs">
                            {(result.numeric_accuracy * 100).toFixed(1)}% accuracy
                          </Badge>
                        </div>
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-5">
                      <div className="rounded-xl border border-white/5 bg-ink/70 p-5 text-sm leading-relaxed text-parchment shadow-inner font-light">
                        {result.summary}
                      </div>

                      {result.warnings.length > 0 && (
                        <div className="space-y-2">
                          <h4 className="text-xs font-semibold uppercase tracking-wider text-hazard">Verification Warnings</h4>
                          {result.warnings.map((w, i) => (
                            <Alert key={i} variant="warning" className="text-xs">
                              {w}
                            </Alert>
                          ))}
                        </div>
                      )}

                      {result.extracted_facts.length > 0 && (
                        <div>
                          <h4 className="mb-3 text-xs font-semibold uppercase tracking-wider text-cortex">
                            Fact Mapping &amp; Cell Provenance ({result.extracted_facts.filter((f) => f.status === "verified").length} matched)
                          </h4>
                          <div className="max-h-60 overflow-auto rounded-xl border border-white/5 bg-ink/30">
                            <table className="w-full text-left text-xs border-collapse">
                              <thead className="sticky top-0 bg-ink/90 text-parchment border-b border-white/10">
                                <tr>
                                  <th className="px-3 py-2 font-medium">Narrative Fact</th>
                                  <th className="px-3 py-2 font-medium">Source Cell Value</th>
                                  <th className="px-3 py-2 font-medium text-right">Status</th>
                                </tr>
                              </thead>
                              <tbody>
                                {result.extracted_facts.slice(0, 50).map((f: any, i: number) => (
                                  <tr key={i} className="border-t border-white/5 hover:bg-white/[0.02]">
                                    <td className="px-3 py-2 font-mono text-accent text-xs">{String(f.value)}</td>
                                    <td className="px-3 py-2 text-cortex">
                                      <span className="text-parchment font-medium text-xs">{String(f.source_label || "Header N")}</span> = {String(f.source_value_repr || "—")}
                                    </td>
                                    <td className="px-3 py-2 text-right">
                                      <Badge variant={f.status === "verified" ? "success" : "warning"} className="text-[10px] uppercase font-semibold">
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
                <Card className="flex h-full min-h-[320px] flex-col items-center justify-center glass-card text-center p-6">
                  <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-white/5 animate-pulse">
                    <Sparkles className="h-8 w-8 text-cortex/50" />
                  </div>
                  <p className="text-cortex max-w-sm">Enter table data and run the NIM engine to generate regulatory narrative and math audit reports.</p>
                </Card>
              )}
            </div>
          </motion.div>
        ) : (
          /* CSR PDF Pipeline workspace */
          <div className="space-y-8">
            {!csrResult ? (
              /* Config & Upload / Progress View */
              <div className="grid gap-8 lg:grid-cols-2">
                <Card className="glass-card">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-xl">
                      <FileText className="h-5 w-5 text-accent" />
                      CSR Document Pipeline
                    </CardTitle>
                    <CardDescription>
                      Upload a complete Clinical Study Report PDF. The pipeline will automatically segment the document, extract tables, run summaries in parallel, perform verification, and generate deliverable DOCX reports.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-5">
                    <div>
                      <label className="mb-1.5 block text-sm font-medium text-cortex">Model</label>
                      <Input value={model} onChange={(e) => setModel(e.target.value)} className="bg-ink/50" />
                    </div>
                    <div>
                      <label className="mb-1.5 block text-sm font-medium text-cortex font-medium">Select CSR PDF</label>
                      <input
                        type="file"
                        accept=".pdf,application/pdf"
                        onChange={(e) => setCsrFile(e.target.files?.[0] || null)}
                        disabled={csrProcessing}
                        className="block w-full rounded-xl border border-white/10 bg-ink/50 px-4 py-3 text-sm text-parchment file:mr-4 file:rounded-lg file:border-0 file:bg-accent file:px-4 file:py-2 file:text-white file:transition-colors hover:file:bg-blue-500 disabled:opacity-50"
                      />
                    </div>
                    <Button
                      onClick={handleCSRUpload}
                      isLoading={csrProcessing && !csrTaskId}
                      disabled={!csrFile || csrProcessing}
                      className="w-full bg-gradient-to-r from-accent to-blue-600 hover:from-blue-500 hover:to-blue-700 font-semibold"
                    >
                      <FileUp className="mr-2 h-4 w-4" /> Start Pipeline Run
                    </Button>
                  </CardContent>
                </Card>

                <Card className="glass-card flex flex-col justify-between">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-xl">
                      <Clock className="h-5 w-5 text-accent" />
                      Pipeline Run Status
                    </CardTitle>
                    <CardDescription>Monitor parsing, generation, and quality audits.</CardDescription>
                  </CardHeader>
                  <CardContent className="flex-1 flex flex-col justify-center space-y-5">
                    {!csrProgress && (
                      <div className="flex h-48 flex-col items-center justify-center text-center">
                        <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-white/5">
                          <FileText className="h-7 w-7 text-cortex/40" />
                        </div>
                        <p className="text-cortex max-w-xs text-sm">Upload a clinical study report PDF to begin processing.</p>
                      </div>
                    )}
                    {csrProgress && (
                      <div className="space-y-4">
                        <div className="flex items-center justify-between text-sm">
                          <span className="capitalize font-semibold text-accent">{csrProgress.stage}</span>
                          <span className="text-cortex">
                            {csrProgress.current}/{csrProgress.total} items
                          </span>
                        </div>
                        <ProgressBar value={csrProgress.progress} />
                        <p className="text-sm font-medium text-parchment flex items-center gap-2">
                          <Loader2 className="h-4 w-4 animate-spin text-accent" />
                          {csrProgress.message}
                        </p>
                        <div className="grid grid-cols-2 gap-4 border-t border-white/5 pt-4 text-xs text-cortex">
                          <div>
                            <span className="block text-[10px] uppercase">Elapsed Time</span>
                            <span className="font-mono text-sm text-parchment">{csrProgress.elapsed_seconds}s</span>
                          </div>
                          <div>
                            <span className="block text-[10px] uppercase">Estimated Remaining</span>
                            <span className="font-mono text-sm text-parchment">{csrProgress.eta_seconds}s</span>
                          </div>
                        </div>
                      </div>
                    )}
                  </CardContent>
                </Card>
              </div>
            ) : (
              /* Completed Rich Workspace View */
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="space-y-6"
              >
                {/* Header overview banner */}
                <div className="flex flex-col gap-6 rounded-2xl border border-white/5 bg-white/[0.02] p-6 backdrop-blur-md md:flex-row md:items-center md:justify-between">
                  <div className="space-y-1">
                    <span className="text-xs uppercase tracking-widest text-cortex font-bold">CSR Summary Result</span>
                    <h2 className="text-2xl font-bold text-parchment truncate max-w-xl">{csrResult.filename}</h2>
                    <p className="text-xs text-cortex">
                      Processed in {((csrResult.total_inference_time_ms || 0) / 1000).toFixed(1)}s &bull; Model: {model.split("/").pop()}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      onClick={() => downloadCSRFile(api.downloadCSRDocx, `csr-deliverable-${Date.now()}.docx`)}
                      className="bg-gradient-to-r from-verified to-emerald-600 hover:from-emerald-500 hover:to-emerald-700 font-semibold"
                    >
                      <Download className="mr-2 h-4 w-4" /> Deliverable DOCX
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() => downloadCSRFile(api.downloadCSRQcReport, `csr-qc-report-${Date.now()}.docx`)}
                      className="border-white/10 bg-white/5 hover:border-accent hover:bg-accent text-parchment font-medium"
                    >
                      <Download className="mr-2 h-4 w-4" /> QC Report
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() => downloadCSRFile(api.downloadCSRAuditLog, `csr-audit-${Date.now()}.json`)}
                      className="border-white/10 bg-white/5 hover:border-accent hover:bg-accent text-parchment font-medium"
                    >
                      <Download className="mr-2 h-4 w-4" /> Audit JSON
                    </Button>
                    <Button
                      variant="ghost"
                      onClick={() => {
                        setCsrResult(null);
                        setCsrProgress(null);
                        setCsrFile(null);
                      }}
                      className="text-cortex hover:text-parchment hover:bg-white/5"
                    >
                      Upload New
                    </Button>
                  </div>
                </div>

                {/* KPI Metrics Widgets */}
                <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                  <div className="rounded-xl border border-white/5 bg-ink/40 p-4 backdrop-blur-md">
                    <p className="text-[10px] uppercase tracking-wider text-cortex font-bold">Total Pages</p>
                    <p className="mt-1 text-2xl font-bold text-parchment">{csrResult.total_pages}</p>
                  </div>
                  <div className="rounded-xl border border-white/5 bg-ink/40 p-4 backdrop-blur-md">
                    <p className="text-[10px] uppercase tracking-wider text-cortex font-bold">Tables Summarized</p>
                    <p className="mt-1 text-2xl font-bold text-parchment">{csrResult.total_tables}</p>
                  </div>
                  <div className="rounded-xl border border-white/5 bg-ink/40 p-4 backdrop-blur-md">
                    <p className="text-[10px] uppercase tracking-wider text-cortex font-bold">Math Verified</p>
                    <p className="mt-1 text-2xl font-bold text-verified">
                      {csrResult.verified_tables} / {csrResult.total_tables}
                    </p>
                  </div>
                  <div className="rounded-xl border border-white/5 bg-ink/40 p-4 backdrop-blur-md">
                    <p className="text-[10px] uppercase tracking-wider text-cortex font-bold">Overall Accuracy</p>
                    <p className="mt-1 text-2xl font-bold text-accent">
                      {(csrResult.overall_numeric_accuracy * 100).toFixed(1)}%
                    </p>
                  </div>
                </div>

                {/* Workspace tab selectors */}
                <div className="flex border-b border-white/5 gap-2">
                  <button
                    onClick={() => setActiveResultTab("synthesis")}
                    className={`pb-3 px-4 text-sm font-semibold border-b-2 transition-all ${
                      activeResultTab === "synthesis"
                        ? "border-accent text-accent"
                        : "border-transparent text-cortex hover:text-parchment"
                    }`}
                  >
                    Document Synthesis
                  </button>
                  <button
                    onClick={() => setActiveResultTab("quality")}
                    className={`pb-3 px-4 text-sm font-semibold border-b-2 transition-all flex items-center gap-1.5 ${
                      activeResultTab === "quality"
                        ? "border-accent text-accent"
                        : "border-transparent text-cortex hover:text-parchment"
                    }`}
                  >
                    Quality Auditing
                    {csrResult.quality_report && !csrResult.quality_report.passed_blocking && (
                      <span className="h-2 w-2 rounded-full bg-red-500 animate-pulse" />
                    )}
                  </button>
                  <button
                    onClick={() => setActiveResultTab("sections")}
                    className={`pb-3 px-4 text-sm font-semibold border-b-2 transition-all ${
                      activeResultTab === "sections"
                        ? "border-accent text-accent"
                        : "border-transparent text-cortex hover:text-parchment"
                    }`}
                  >
                    ICH E3 Section Explorer
                  </button>
                </div>

                {/* Tab Content rendering */}
                <div className="mt-4">
                  {/* TAB 1: Document Synthesis */}
                  {activeResultTab === "synthesis" && (
                    <motion.div initial={{ opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }} className="space-y-6">
                      <Card className="glass-card">
                        <CardHeader>
                          <CardTitle className="text-lg text-parchment font-semibold">Executive Narrative Overview</CardTitle>
                          <CardDescription>Synthesized regulatory overview mapping findings across the clinical study report.</CardDescription>
                        </CardHeader>
                        <CardContent>
                          <div className="rounded-xl border border-white/5 bg-ink/60 p-6 leading-relaxed text-parchment font-light text-sm whitespace-pre-line">
                            {csrResult.document_synthesis}
                          </div>
                        </CardContent>
                      </Card>
                    </motion.div>
                  )}

                  {/* TAB 2: Quality Checks & Consistency */}
                  {activeResultTab === "quality" && (
                    <motion.div initial={{ opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }} className="space-y-6">
                      {/* Consistency discrepancies */}
                      <Card className="glass-card">
                        <CardHeader>
                          <CardTitle className="text-lg text-parchment font-semibold">Cross-Table N-Value Consistency</CardTitle>
                          <CardDescription>Validates study patient counts (N values) for defined treatment groups across all safety and efficacy tables.</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-4">
                          {csrResult.consistency_warnings && csrResult.consistency_warnings.length > 0 ? (
                            <div className="space-y-3">
                              {csrResult.consistency_warnings.map((w: any, idx: number) => (
                                <div key={idx} className="flex gap-3 rounded-xl border border-amber-500/20 bg-amber-500/5 p-4 text-xs">
                                  <AlertTriangle className="h-5 w-5 shrink-0 text-amber-500" />
                                  <div>
                                    <h5 className="font-semibold text-parchment uppercase tracking-wide">
                                      Discrepancy: {w.category.replace("_", " ")}
                                    </h5>
                                    <p className="mt-1 text-cortex leading-relaxed">{w.message}</p>
                                    <p className="mt-2 text-[10px] text-cortex/50">
                                      Source Tables: {w.source_tables.join(", ")}
                                    </p>
                                  </div>
                                </div>
                              ))}
                            </div>
                          ) : (
                            <div className="flex items-center gap-2 rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-4 text-sm text-verified">
                              <CheckCircle className="h-5 w-5" />
                              <span>No N-value discrepancies detected across treatment arms. Patient counts are consistent.</span>
                            </div>
                          )}
                        </CardContent>
                      </Card>

                      {/* Automated pre-review checks list */}
                      {csrResult.quality_report && (
                        <Card className="glass-card">
                          <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-4 pb-4">
                            <div>
                              <CardTitle className="text-lg text-parchment font-semibold">Automated Quality Review Audits</CardTitle>
                              <CardDescription>Pre-review validation rules mapping style, statistical criteria, populations, and accuracy.</CardDescription>
                            </div>
                            <div>
                              {csrResult.quality_report.passed_blocking ? (
                                <Badge variant="success" className="px-3 py-1 font-semibold">
                                  PASSES BLOCKING CHECKS
                                </Badge>
                              ) : (
                                <Badge variant="error" className="px-3 py-1 font-semibold">
                                  BLOCKING FAILS FOUND
                                </Badge>
                              )}
                            </div>
                          </CardHeader>
                          <CardContent className="space-y-4">
                            {/* Checklist cards */}
                            <div className="space-y-3">
                              {csrResult.quality_report.findings.map((f: any, idx: number) => {
                                const isFail = f.status === "FAIL";
                                const isWarning = f.status === "WARNING";
                                return (
                                  <div
                                    key={idx}
                                    className={`flex gap-3 rounded-xl border p-4 text-xs transition-colors ${
                                      isFail
                                        ? "border-red-500/20 bg-red-500/[0.02]"
                                        : isWarning
                                        ? "border-amber-500/20 bg-amber-500/[0.02]"
                                        : "border-white/5 bg-white/[0.01]"
                                    }`}
                                  >
                                    <div className="mt-0.5 shrink-0">
                                      {isFail && <XCircle className="h-4.5 w-4.5 text-red-500" />}
                                      {isWarning && <AlertTriangle className="h-4.5 w-4.5 text-amber-500" />}
                                      {f.status === "PASS" && <CheckCircle className="h-4.5 w-4.5 text-verified" />}
                                    </div>
                                    <div className="flex-1 space-y-1">
                                      <div className="flex flex-wrap items-center gap-2">
                                        <span className="font-semibold text-parchment">{f.name}</span>
                                        <Badge className="text-[9px] uppercase tracking-wider scale-90" variant={isFail ? "error" : isWarning ? "warning" : "success"}>
                                          {f.check_id}
                                        </Badge>
                                        <span className="text-[10px] text-cortex/50">Rule: {f.type}</span>
                                      </div>
                                      <p className="text-cortex text-xs leading-relaxed">{f.message}</p>
                                      {f.suggestion && (
                                        <p className="text-[11px] font-medium text-accent">
                                          Recommendation: {f.suggestion}
                                        </p>
                                      )}
                                      {f.flagged_text && (
                                        <div className="mt-2 rounded-lg border border-white/5 bg-ink/50 p-2 font-mono text-[10px] text-cortex">
                                          Flagged Segment: {f.flagged_text}
                                        </div>
                                      )}
                                      <div className="mt-1 flex items-center gap-4 text-[10px] text-cortex/40">
                                        {f.source_table_id && <span>Source Table: {f.source_table_id}</span>}
                                        {f.source_section && <span>ICH Section: {f.source_section}</span>}
                                      </div>
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                          </CardContent>
                        </Card>
                      )}
                    </motion.div>
                  )}

                  {/* TAB 3: Section Explorer */}
                  {activeResultTab === "sections" && (
                    <motion.div initial={{ opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
                      {csrResult.sections.map((section: any) => {
                        const isExpanded = !!expandedSections[section.section_number];
                        return (
                          <div
                            key={section.section_number}
                            className="rounded-2xl border border-white/5 bg-white/[0.01] overflow-hidden"
                          >
                            {/* Accordion Header */}
                            <button
                              onClick={() => toggleSection(section.section_number)}
                              className="w-full flex items-center justify-between p-5 text-left hover:bg-white/[0.02] transition-colors"
                            >
                              <div className="flex items-center gap-4 min-w-0">
                                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-accent/10 text-xs font-semibold text-accent">
                                  {section.section_number}
                                </div>
                                <div className="min-w-0">
                                  <h4 className="text-base font-semibold text-parchment truncate">{section.canonical_title}</h4>
                                  <p className="text-xs text-cortex/60">
                                    Pages {section.start_page}–{section.end_page} &bull; {section.tables_found} tables
                                  </p>
                                </div>
                              </div>
                              <div className="flex items-center gap-3 shrink-0">
                                <Badge variant="info" className="text-xs px-2.5 py-0.5">
                                  {(section.accuracy * 100).toFixed(1)}% accuracy
                                </Badge>
                                {isExpanded ? <ChevronUp className="h-5 w-5 text-cortex" /> : <ChevronDown className="h-5 w-5 text-cortex" />}
                              </div>
                            </button>

                            {/* Accordion Content */}
                            {isExpanded && (
                              <div className="border-t border-white/5 bg-ink/20 p-5 space-y-6">
                                {/* Section synthesis prose */}
                                {section.section_synthesis && (
                                  <div className="space-y-2">
                                    <h5 className="text-xs font-semibold uppercase tracking-wider text-accent">Section Narrative Synthesis</h5>
                                    <div className="rounded-xl border border-white/5 bg-ink/50 p-4 text-sm leading-relaxed text-parchment font-light">
                                      {section.section_synthesis}
                                    </div>
                                  </div>
                                )}

                                {/* Key Findings list */}
                                {section.key_findings && section.key_findings.length > 0 && (
                                  <div className="space-y-2">
                                    <h5 className="text-xs font-semibold uppercase tracking-wider text-cortex">Key Quantitative Findings</h5>
                                    <ul className="list-inside list-disc pl-2 space-y-1.5 text-xs text-cortex">
                                      {section.key_findings.map((f: string, fIdx: number) => (
                                        <li key={fIdx} className="leading-relaxed">
                                          <span className="text-parchment font-light">{f}</span>
                                        </li>
                                      ))}
                                    </ul>
                                  </div>
                                )}

                                {/* Tables summaries inside the section */}
                                <div className="space-y-4 pt-2">
                                  <h5 className="text-xs font-semibold uppercase tracking-wider text-cortex">Individual Table Summaries</h5>
                                  <div className="space-y-3">
                                    {section.table_summaries.map((tr: any) => {
                                      const isTableExpanded = !!expandedTables[tr.table_id];
                                      return (
                                        <div
                                          key={tr.table_id}
                                          className="rounded-xl border border-white/5 bg-white/[0.01]"
                                        >
                                          <button
                                            onClick={() => toggleTable(tr.table_id)}
                                            className="w-full flex items-center justify-between p-4 text-left hover:bg-white/[0.02] transition-colors text-xs"
                                          >
                                            <div className="min-w-0">
                                              <span className="font-semibold text-parchment">{tr.title || "Untitled Table"}</span>
                                              <span className="ml-2 text-cortex font-mono text-[10px]">({tr.table_id})</span>
                                              <p className="mt-0.5 text-[10px] text-cortex/50">Type: {tr.table_type} &bull; Page: {tr.page}</p>
                                            </div>
                                            <div className="flex items-center gap-3 shrink-0">
                                              <Badge variant={tr.verified ? "success" : "warning"} className="text-[10px] px-2">
                                                {tr.verified ? "Verified" : "Review"}
                                              </Badge>
                                              <span className="text-cortex font-mono text-[10px]">{(tr.numeric_accuracy * 100).toFixed(0)}% acc</span>
                                              {isTableExpanded ? <ChevronUp className="h-4 w-4 text-cortex" /> : <ChevronDown className="h-4 w-4 text-cortex" />}
                                            </div>
                                          </button>

                                          {isTableExpanded && (
                                            <div className="border-t border-white/5 bg-ink/40 p-4 space-y-4 text-xs">
                                              <div className="space-y-1.5">
                                                <span className="font-semibold text-accent text-[10px] uppercase">Table Summary Narrative</span>
                                                <p className="text-parchment leading-relaxed font-light">{tr.summary}</p>
                                              </div>

                                              {tr.warnings && tr.warnings.length > 0 && (
                                                <div className="space-y-1">
                                                  <span className="font-semibold text-hazard text-[10px] uppercase">Warnings</span>
                                                  {tr.warnings.map((w: string, idx: number) => (
                                                    <p key={idx} className="text-hazard font-mono text-[10px]">⚠ {w}</p>
                                                  ))}
                                                </div>
                                              )}

                                              {/* Facts Provenance Grid inside Table */}
                                              {tr.extracted_facts && tr.extracted_facts.length > 0 && (
                                                <div className="space-y-2">
                                                  <span className="font-semibold text-cortex text-[10px] uppercase block">Narrative-to-Table Math Provenance</span>
                                                  <div className="max-h-52 overflow-auto rounded-lg border border-white/5 bg-ink/70">
                                                    <table className="w-full text-left text-[11px] border-collapse">
                                                      <thead className="sticky top-0 bg-ink/90 text-parchment border-b border-white/10">
                                                        <tr>
                                                          <th className="px-3 py-1.5 font-medium">Fact Value</th>
                                                          <th className="px-3 py-1.5 font-medium">Grid Source Alignment</th>
                                                          <th className="px-3 py-1.5 font-medium text-right">Verification</th>
                                                        </tr>
                                                      </thead>
                                                      <tbody>
                                                        {tr.extracted_facts.map((f: any, factIdx: number) => (
                                                          <tr key={factIdx} className="border-t border-white/5 hover:bg-white/[0.01]">
                                                            <td className="px-3 py-1.5 font-mono text-accent">{String(f.value)}</td>
                                                            <td className="px-3 py-1.5 text-cortex leading-tight">
                                                              <span className="text-parchment font-medium">{String(f.source_label || "Header")}</span> = {String(f.source_value_repr || "—")}
                                                            </td>
                                                            <td className="px-3 py-1.5 text-right">
                                                              <Badge variant={f.status === "verified" ? "success" : "warning"} className="text-[9px] uppercase font-semibold scale-90">
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
                                            </div>
                                          )}
                                        </div>
                                      );
                                    })}
                                  </div>
                                </div>
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </motion.div>
                  )}
                </div>
              </motion.div>
            )}
          </div>
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
