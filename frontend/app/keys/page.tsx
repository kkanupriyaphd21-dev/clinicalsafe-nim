"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Alert } from "@/components/ui/alert";
import { NeuralBackground } from "@/components/ui/neural-background";
import { api, APIKey } from "@/lib/api";
import {
  ArrowLeft,
  Plus,
  Trash2,
  Star,
  Activity,
  Shield,
  Lock,
  KeyRound,
  CheckCircle2,
  Power,
} from "lucide-react";

export default function KeysPage() {
  const [keys, setKeys] = useState<APIKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [newName, setNewName] = useState("");
  const [newKey, setNewKey] = useState("");
  const [isDefault, setIsDefault] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const fetchKeys = async () => {
    try {
      const data = await api.listKeys();
      setKeys(data.keys);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load keys");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchKeys();
  }, []);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim() || !newKey.trim()) return;
    setSubmitting(true);
    try {
      await api.createKey({ name: newName, key: newKey, is_default: isDefault });
      setNewName("");
      setNewKey("");
      setIsDefault(false);
      await fetchKeys();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to add key");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this API key?")) return;
    try {
      await api.deleteKey(id);
      await fetchKeys();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete key");
    }
  };

  const handleSetDefault = async (id: string) => {
    try {
      await api.updateKey(id, { is_default: true });
      await fetchKeys();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to update key");
    }
  };

  const handleToggleActive = async (key: APIKey) => {
    try {
      await api.updateKey(key.id, { is_active: !key.is_active });
      await fetchKeys();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to update key");
    }
  };

  return (
    <main className="relative min-h-screen overflow-hidden bg-clinical">
      <NeuralBackground />

      <header className="relative border-b border-white/5 bg-ink/40 backdrop-blur-xl">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-4">
            <Link href="/">
              <Button variant="ghost" size="sm" className="text-cortex hover:text-parchment">
                <ArrowLeft className="mr-2 h-4 w-4" /> Back
              </Button>
            </Link>
            <h1 className="text-xl font-bold text-parchment">API Key Vault</h1>
          </div>
        </div>
      </header>

      <div className="relative mx-auto max-w-6xl px-6 py-10">
        {error && (
          <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
            <Alert variant="error" className="mb-6">
              {error}
            </Alert>
          </motion.div>
        )}

        <div className="grid gap-8 md:grid-cols-[1fr_1.6fr]">
          {/* Add key form */}
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.4 }}
          >
            <Card className="glass-card">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-xl">
                  <KeyRound className="h-5 w-5 text-accent" />
                  Add NVIDIA API Key
                </CardTitle>
                <CardDescription>
                  Keys are encrypted at rest with your MASTER_KEY and never returned in full.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleAdd} className="space-y-5">
                  <div>
                    <label className="mb-1.5 block text-sm font-medium text-cortex">Key name</label>
                    <Input
                      placeholder="e.g. Production Key"
                      value={newName}
                      onChange={(e) => setNewName(e.target.value)}
                      required
                      className="bg-ink/50"
                    />
                  </div>
                  <div>
                    <label className="mb-1.5 block text-sm font-medium text-cortex">NVIDIA API key</label>
                    <Input
                      type="password"
                      placeholder="nvapi-..."
                      value={newKey}
                      onChange={(e) => setNewKey(e.target.value)}
                      required
                      className="bg-ink/50"
                    />
                  </div>
                  <label className="flex items-center gap-3 rounded-xl border border-white/5 bg-ink/30 p-3 text-sm text-parchment transition-colors hover:bg-ink/50">
                    <input
                      type="checkbox"
                      checked={isDefault}
                      onChange={(e) => setIsDefault(e.target.checked)}
                      className="rounded border-surface-2 bg-ink text-accent"
                    />
                    <Star className="h-4 w-4 text-amber-400" />
                    Set as default key
                  </label>
                  <Button
                    type="submit"
                    isLoading={submitting}
                    className="w-full bg-gradient-to-r from-accent to-blue-600 hover:from-blue-500 hover:to-blue-700"
                  >
                    <Plus className="mr-2 h-4 w-4" /> Add Key
                  </Button>
                </form>
              </CardContent>
            </Card>
          </motion.div>

          {/* Key list */}
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.4, delay: 0.1 }}
          >
            <Card className="glass-card">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-xl">
                  <Shield className="h-5 w-5 text-accent" />
                  Stored Keys
                </CardTitle>
                <CardDescription>Manage active keys, monitor usage, and control rotation.</CardDescription>
              </CardHeader>
              <CardContent>
                {loading ? (
                  <div className="flex h-40 items-center justify-center">
                    <div className="h-8 w-8 animate-spin rounded-full border-2 border-accent border-t-transparent" />
                  </div>
                ) : keys.length === 0 ? (
                  <div className="flex h-40 flex-col items-center justify-center rounded-xl border border-dashed border-white/10 bg-ink/30 text-center">
                    <Lock className="mb-2 h-8 w-8 text-cortex" />
                    <p className="text-cortex">No keys stored yet. Add one to get started.</p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {keys.map((key, index) => (
                      <motion.div
                        key={key.id}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: index * 0.05 }}
                        className="flex flex-col gap-4 rounded-xl border border-white/5 bg-ink/40 p-5 transition-colors hover:border-accent/30 hover:bg-ink/60 sm:flex-row sm:items-start sm:justify-between"
                      >
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="truncate font-semibold text-parchment">{key.name}</p>
                            {key.is_default && (
                              <Badge variant="info" className="px-2 py-0.5">
                                <Star className="mr-1 h-3 w-3" /> Default
                              </Badge>
                            )}
                            {key.is_active ? (
                              <Badge variant="success" className="px-2 py-0.5">
                                <CheckCircle2 className="mr-1 h-3 w-3" /> Active
                              </Badge>
                            ) : (
                              <Badge variant="error" className="px-2 py-0.5">
                                Inactive
                              </Badge>
                            )}
                          </div>
                          <p className="mt-2 font-mono text-sm text-cortex">{key.masked_key}</p>
                          <div className="mt-3 flex flex-wrap items-center gap-4 text-xs text-cortex">
                            <span className="flex items-center gap-1">
                              <Activity className="h-3.5 w-3.5 text-accent" />
                              {key.usage_total_requests} requests
                            </span>
                            <span>{key.usage_total_tokens.toLocaleString()} tokens</span>
                            {key.last_used_at && (
                              <span>Last used {new Date(key.last_used_at).toLocaleString()}</span>
                            )}
                          </div>
                        </div>
                        <div className="flex flex-wrap gap-2 sm:flex-col sm:items-end">
                          {!key.is_default && key.is_active && (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleSetDefault(key.id)}
                              className="border-white/10 bg-white/5 hover:border-accent/50 hover:bg-accent/10"
                            >
                              <Star className="mr-1 h-3.5 w-3.5" /> Set default
                            </Button>
                          )}
                          <div className="flex gap-2">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleToggleActive(key)}
                              className="text-cortex hover:text-parchment"
                            >
                              <Power className="mr-1 h-3.5 w-3.5" />
                              {key.is_active ? "Deactivate" : "Activate"}
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="text-red-400 hover:bg-red-500/10 hover:text-red-300"
                              onClick={() => handleDelete(key.id)}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </div>
                      </motion.div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </motion.div>
        </div>
      </div>
    </main>
  );
}
