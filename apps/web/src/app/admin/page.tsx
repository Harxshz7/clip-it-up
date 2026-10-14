"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  BarChart3,
  TrendingUp,
  DollarSign,
  ShieldAlert,
  Activity,
  Users,
  Film,
  Download,
  Key,
  Trash2,
  Plus,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  Clock,
  Layers,
  Loader2,
} from "lucide-react";
import { api } from "@/lib/api";
import {
  FunnelMetricsResponse,
  ProductHealthMetricsResponse,
  MoneyMetricsResponse,
  AbuseMetricsResponse,
} from "@clip-it-up/shared";

export default function AdminDashboardPage() {
  const [tab, setTab] = useState<"funnel" | "health" | "money" | "abuse" | "invites">("funnel");
  const [loading, setLoading] = useState(true);
  const [funnel, setFunnel] = useState<FunnelMetricsResponse | null>(null);
  const [health, setHealth] = useState<ProductHealthMetricsResponse | null>(null);
  const [money, setMoney] = useState<MoneyMetricsResponse | null>(null);
  const [abuse, setAbuse] = useState<AbuseMetricsResponse | null>(null);
  const [invites, setInvites] = useState<any[]>([]);
  const [newInviteCode, setNewInviteCode] = useState("");
  const [newInviteUses, setNewInviteUses] = useState(25);
  const [exportMonth, setExportMonth] = useState("2026-10");
  const [actionLoading, setActionLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const fetchMetrics = async () => {
    try {
      setLoading(true);
      const [f, h, m, a, inv] = await Promise.all([
        api.getAdminFunnelMetrics().catch(() => null),
        api.getAdminProductHealthMetrics().catch(() => null),
        api.getAdminMoneyMetrics().catch(() => null),
        api.getAdminAbuseMetrics().catch(() => null),
        api.getAdminInvites().catch(() => []),
      ]);

      setFunnel(f);
      setHealth(h);
      setMoney(m);
      setAbuse(a);
      setInvites(inv);
    } catch (err: any) {
      console.error("Admin fetch error:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMetrics();
  }, []);

  const handleCreateInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newInviteCode.trim()) return;
    try {
      setActionLoading(true);
      await api.createAdminInvite({
        code: newInviteCode.trim().toUpperCase(),
        max_uses: newInviteUses,
        expires_in_days: 30,
      });
      setNewInviteCode("");
      setMessage("Invite code created successfully!");
      await fetchMetrics();
    } catch (err: any) {
      alert(err.message || "Failed to create invite code");
    } finally {
      setActionLoading(false);
    }
  };

  const handleRevokeInvite = async (code: string) => {
    if (!confirm(`Revoke invite code ${code}?`)) return;
    try {
      await api.revokeAdminInvite(code);
      await fetchMetrics();
    } catch (err: any) {
      alert(err.message || "Failed to revoke code");
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <Loader2 className="w-8 h-8 animate-spin text-purple-400" />
      </div>
    );
  }

  return (
    <div className="space-y-8 pb-16">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-indigo-500/10 text-indigo-300 text-xs font-semibold border border-indigo-500/20 mb-2">
            <ShieldAlert className="w-3.5 h-3.5 text-indigo-400" />
            <span>Admin Control Panel (Audited)</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
            System Intelligence & Ops
          </h1>
          <p className="text-xs sm:text-sm text-zinc-400 mt-1">
            Realtime conversion funnel, worker health, MRR revenue vs costs, abuse mitigation, and invite gating.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={fetchMetrics}
            className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.03] px-3.5 py-2 text-xs font-semibold text-zinc-300 hover:text-white hover:bg-white/10 transition-all"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {message && (
        <div className="p-3.5 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs flex items-center justify-between">
          <span>{message}</span>
          <button onClick={() => setMessage(null)} className="text-zinc-400 hover:text-white">✕</button>
        </div>
      )}

      {/* Tabs */}
      <div className="flex items-center gap-2 border-b border-white/10 pb-3 overflow-x-auto">
        <button
          onClick={() => setTab("funnel")}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all ${
            tab === "funnel" ? "bg-purple-600 text-white shadow-md shadow-purple-500/25" : "text-zinc-400 hover:text-white hover:bg-white/5"
          }`}
        >
          <TrendingUp className="w-4 h-4" /> Funnel Conversion
        </button>

        <button
          onClick={() => setTab("health")}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all ${
            tab === "health" ? "bg-purple-600 text-white shadow-md shadow-purple-500/25" : "text-zinc-400 hover:text-white hover:bg-white/5"
          }`}
        >
          <Activity className="w-4 h-4" /> Product Health
        </button>

        <button
          onClick={() => setTab("money")}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all ${
            tab === "money" ? "bg-purple-600 text-white shadow-md shadow-purple-500/25" : "text-zinc-400 hover:text-white hover:bg-white/5"
          }`}
        >
          <DollarSign className="w-4 h-4" /> Money & Margin
        </button>

        <button
          onClick={() => setTab("abuse")}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all ${
            tab === "abuse" ? "bg-purple-600 text-white shadow-md shadow-purple-500/25" : "text-zinc-400 hover:text-white hover:bg-white/5"
          }`}
        >
          <ShieldAlert className="w-4 h-4" /> Abuse & DMCA
        </button>

        <button
          onClick={() => setTab("invites")}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all ${
            tab === "invites" ? "bg-purple-600 text-white shadow-md shadow-purple-500/25" : "text-zinc-400 hover:text-white hover:bg-white/5"
          }`}
        >
          <Key className="w-4 h-4" /> Invite Gating
        </button>
      </div>

      {/* 1. Funnel View */}
      {tab === "funnel" && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-4">
            <div className="glass-panel rounded-2xl p-4 border border-white/5">
              <span className="text-[11px] text-zinc-400 uppercase tracking-wider font-semibold">1. Visitors</span>
              <div className="text-2xl font-bold text-white mt-1">{funnel?.total_visitors || 0}</div>
            </div>
            <div className="glass-panel rounded-2xl p-4 border border-white/5">
              <span className="text-[11px] text-zinc-400 uppercase tracking-wider font-semibold">2. Signups</span>
              <div className="text-2xl font-bold text-white mt-1">{funnel?.signups || 0}</div>
              <span className="text-[10px] text-purple-300 font-medium">{funnel?.conversion_rates?.visitor_to_signup_pct || 0}% conv</span>
            </div>
            <div className="glass-panel rounded-2xl p-4 border border-white/5">
              <span className="text-[11px] text-zinc-400 uppercase tracking-wider font-semibold">3. Uploads</span>
              <div className="text-2xl font-bold text-white mt-1">{funnel?.uploads || 0}</div>
              <span className="text-[10px] text-purple-300 font-medium">{funnel?.conversion_rates?.signup_to_upload_pct || 0}% conv</span>
            </div>
            <div className="glass-panel rounded-2xl p-4 border border-white/5">
              <span className="text-[11px] text-zinc-400 uppercase tracking-wider font-semibold">4. 1st Export</span>
              <div className="text-2xl font-bold text-white mt-1">{funnel?.first_exports || 0}</div>
              <span className="text-[10px] text-purple-300 font-medium">{funnel?.conversion_rates?.upload_to_export_pct || 0}% conv</span>
            </div>
            <div className="glass-panel rounded-2xl p-4 border border-purple-500/30 bg-purple-950/20">
              <span className="text-[11px] text-purple-300 uppercase tracking-wider font-semibold">5. Paid Subs</span>
              <div className="text-2xl font-bold text-white mt-1">{funnel?.paid_subscribers || 0}</div>
              <span className="text-[10px] text-emerald-400 font-semibold">{funnel?.conversion_rates?.export_to_paid_pct || 0}% paid</span>
            </div>
          </div>

          <div className="glass-panel rounded-3xl p-6 border border-white/5 space-y-4">
            <h3 className="text-sm font-bold text-white">Full Funnel Conversion Walkthrough</h3>
            <div className="space-y-3">
              {[
                { label: "Landing -> Signup", rate: funnel?.conversion_rates?.visitor_to_signup_pct || 0 },
                { label: "Signup -> First Upload", rate: funnel?.conversion_rates?.signup_to_upload_pct || 0 },
                { label: "Upload -> First Export", rate: funnel?.conversion_rates?.upload_to_export_pct || 0 },
                { label: "Export -> Paid Subscription", rate: funnel?.conversion_rates?.export_to_paid_pct || 0 },
              ].map((step, idx) => (
                <div key={idx} className="space-y-1">
                  <div className="flex justify-between text-xs">
                    <span className="text-zinc-300">{step.label}</span>
                    <span className="font-bold text-white">{step.rate}%</span>
                  </div>
                  <div className="h-2 w-full bg-zinc-800 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-purple-500 to-indigo-500 rounded-full"
                      style={{ width: `${Math.min(100, step.rate)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* 2. Health View */}
      {tab === "health" && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
            <div className="glass-panel rounded-2xl p-4 border border-white/5">
              <span className="text-[11px] text-zinc-400 uppercase font-semibold">Daily Job Volume</span>
              <div className="text-2xl font-bold text-white mt-1">{health?.jobs_per_day || 0}</div>
            </div>
            <div className="glass-panel rounded-2xl p-4 border border-white/5">
              <span className="text-[11px] text-zinc-400 uppercase font-semibold">Pipeline Success Rate</span>
              <div className="text-2xl font-bold text-emerald-400 mt-1">{health?.success_rate || 100}%</div>
            </div>
            <div className="glass-panel rounded-2xl p-4 border border-white/5">
              <span className="text-[11px] text-zinc-400 uppercase font-semibold">Time to First Clips (p50)</span>
              <div className="text-2xl font-bold text-white mt-1">{health?.time_to_first_clips_p50_s || 0}s</div>
            </div>
            <div className="glass-panel rounded-2xl p-4 border border-white/5">
              <span className="text-[11px] text-zinc-400 uppercase font-semibold">Queue Depth</span>
              <div className="text-sm font-bold text-zinc-200 mt-2 flex gap-4">
                <span>CPU: {health?.queue_depth?.cpu || 0}</span>
                <span>GPU: {health?.queue_depth?.gpu || 0}</span>
              </div>
            </div>
          </div>

          <div className="glass-panel rounded-3xl p-6 border border-white/5 space-y-3">
            <h3 className="text-sm font-bold text-white">Error Code Taxonomy Breakdown</h3>
            {health?.error_code_breakdown && Object.keys(health.error_code_breakdown).length > 0 ? (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {Object.entries(health.error_code_breakdown).map(([code, cnt]) => (
                  <div key={code} className="p-3 rounded-xl bg-zinc-900 border border-white/5">
                    <span className="text-[10px] text-red-400 font-mono font-bold">{code}</span>
                    <div className="text-lg font-bold text-white mt-1">{cnt} occurrences</div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-xs text-emerald-400 flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4" />
                <span>Zero system errors recorded in active cycle!</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* 3. Money View */}
      {tab === "money" && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
            <div className="glass-panel rounded-2xl p-4 border border-white/5">
              <span className="text-[11px] text-zinc-400 uppercase font-semibold">Monthly Recurring Revenue</span>
              <div className="text-2xl font-bold text-white mt-1">₹{money?.mrr_inr || 0}</div>
            </div>
            <div className="glass-panel rounded-2xl p-4 border border-white/5">
              <span className="text-[11px] text-zinc-400 uppercase font-semibold">Gross Margin</span>
              <div className="text-2xl font-bold text-emerald-400 mt-1">
                {money?.revenue_vs_cost?.gross_margin_pct || 0}%
              </div>
            </div>
            <div className="glass-panel rounded-2xl p-4 border border-white/5">
              <span className="text-[11px] text-zinc-400 uppercase font-semibold">ARPU</span>
              <div className="text-2xl font-bold text-white mt-1">₹{money?.arpu_inr || 0}</div>
            </div>
            <div className="glass-panel rounded-2xl p-4 border border-white/5">
              <span className="text-[11px] text-zinc-400 uppercase font-semibold">Churn Rate</span>
              <div className="text-2xl font-bold text-zinc-300 mt-1">{money?.churn_rate_pct || 0}%</div>
            </div>
          </div>

          {/* Export Invoices CSV */}
          <div className="glass-panel rounded-3xl p-6 border border-white/5 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <h3 className="text-sm font-bold text-white">Export Monthly Tax Invoices for Accountant</h3>
                <p className="text-xs text-zinc-400">Generates a standard CSV report for GSTR-1 filing and reconciliation.</p>
              </div>

              <div className="flex items-center gap-3">
                <input
                  type="month"
                  value={exportMonth}
                  onChange={(e) => setExportMonth(e.target.value)}
                  className="px-3 py-1.5 rounded-xl bg-zinc-900 border border-white/10 text-xs text-white"
                />
                <a
                  href={api.getAdminInvoicesExportUrl(exportMonth)}
                  download
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 text-xs font-semibold text-white shadow-md transition-all"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Download CSV</span>
                </a>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 4. Abuse View */}
      {tab === "abuse" && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
            <div className="glass-panel rounded-2xl p-4 border border-white/5">
              <span className="text-[11px] text-zinc-400 uppercase font-semibold">Users Near Cap</span>
              <div className="text-2xl font-bold text-amber-300 mt-1">{abuse?.users_near_cap || 0}</div>
            </div>
            <div className="glass-panel rounded-2xl p-4 border border-white/5">
              <span className="text-[11px] text-zinc-400 uppercase font-semibold">Rate Limit Hits (24h)</span>
              <div className="text-2xl font-bold text-white mt-1">{abuse?.rate_limit_hits_24h || 0}</div>
            </div>
            <div className="glass-panel rounded-2xl p-4 border border-white/5">
              <span className="text-[11px] text-zinc-400 uppercase font-semibold">Flagged Uploads</span>
              <div className="text-2xl font-bold text-white mt-1">{abuse?.flagged_uploads || 0}</div>
            </div>
            <div className="glass-panel rounded-2xl p-4 border border-white/5">
              <span className="text-[11px] text-zinc-400 uppercase font-semibold">Active DMCA Queue</span>
              <div className="text-2xl font-bold text-white mt-1">{abuse?.dmca_queue_count || 0}</div>
            </div>
          </div>
        </div>
      )}

      {/* 5. Invite Codes View */}
      {tab === "invites" && (
        <div className="space-y-6">
          <div className="glass-panel rounded-3xl p-6 border border-white/5 space-y-4">
            <h3 className="text-sm font-bold text-white">Create Soft-Launch Invite Code</h3>
            <form onSubmit={handleCreateInvite} className="flex flex-col sm:flex-row items-center gap-3">
              <input
                type="text"
                required
                value={newInviteCode}
                onChange={(e) => setNewInviteCode(e.target.value)}
                placeholder="e.g. VIPCREATOR2026"
                className="w-full sm:w-64 px-3.5 py-2.5 rounded-xl bg-zinc-900 border border-white/10 text-xs text-white uppercase font-mono font-bold focus:outline-none focus:border-purple-500"
              />
              <input
                type="number"
                min={1}
                max={500}
                value={newInviteUses}
                onChange={(e) => setNewInviteUses(parseInt(e.target.value))}
                className="w-full sm:w-32 px-3.5 py-2.5 rounded-xl bg-zinc-900 border border-white/10 text-xs text-white focus:outline-none focus:border-purple-500"
              />
              <button
                type="submit"
                disabled={actionLoading}
                className="w-full sm:w-auto flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-xs font-semibold text-white shadow-md transition-all"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Create Code</span>
              </button>
            </form>
          </div>

          <div className="glass-panel rounded-3xl border border-white/5 overflow-hidden">
            <table className="w-full text-left text-xs text-zinc-300">
              <thead className="bg-white/[0.03] text-zinc-400 uppercase text-[10px] tracking-wider border-b border-white/5">
                <tr>
                  <th className="px-5 py-3">Invite Code</th>
                  <th className="px-5 py-3">Used / Max Uses</th>
                  <th className="px-5 py-3">Expires At</th>
                  <th className="px-5 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {invites.map((inv) => (
                  <tr key={inv.code} className="hover:bg-white/[0.02]">
                    <td className="px-5 py-3.5 font-mono font-bold text-purple-300">{inv.code}</td>
                    <td className="px-5 py-3.5">{inv.used_count} / {inv.max_uses}</td>
                    <td className="px-5 py-3.5 text-zinc-400">
                      {inv.expires_at ? new Date(inv.expires_at).toLocaleDateString() : "Never"}
                    </td>
                    <td className="px-5 py-3.5 text-right">
                      <button
                        onClick={() => handleRevokeInvite(inv.code)}
                        className="text-red-400 hover:text-red-300 p-1.5 rounded-lg hover:bg-red-500/10 transition-colors"
                        title="Revoke code"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
