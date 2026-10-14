"use client";

import { useState } from "react";
import { AlertCircle, CheckCircle2, Shield, Send, Loader2 } from "lucide-react";
import { api } from "@/lib/api";

export default function CopyrightPage() {
  const [formData, setFormData] = useState({
    claimant_name: "",
    claimant_email: "",
    claimant_phone: "",
    claimant_company: "",
    work_description: "",
    infringing_urls_or_ids: "",
    good_faith_statement: false,
    accuracy_statement: false,
    signature: "",
  });

  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState<any | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.good_faith_statement || !formData.accuracy_statement) {
      setError("Please check both affirmation statements to proceed.");
      return;
    }

    try {
      setLoading(true);
      setError(null);
      const urlsOrIds = formData.infringing_urls_or_ids
        .split("\n")
        .map((s) => s.trim())
        .filter(Boolean);

      const res = await api.submitTakedown({
        claimant_name: formData.claimant_name,
        claimant_email: formData.claimant_email,
        claimant_phone: formData.claimant_phone || undefined,
        claimant_company: formData.claimant_company || undefined,
        work_description: formData.work_description,
        infringing_urls_or_ids: urlsOrIds,
        good_faith_statement: formData.good_faith_statement,
        accuracy_statement: formData.accuracy_statement,
        signature: formData.signature,
      });

      setSubmitted(res);
    } catch (err: any) {
      setError(err.message || "Failed to submit takedown request.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto py-10 space-y-10 text-zinc-300 text-sm leading-relaxed">
      {/* Notice Banner */}
      <div className="p-4 rounded-2xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs flex items-center gap-3">
        <AlertCircle className="w-5 h-5 shrink-0" />
        <div>
          <strong>DRAFT - REQUIRES FORMAL LEGAL REVIEW:</strong> DMCA and Indian Copyright Act takedown intake process.
        </div>
      </div>

      <div className="space-y-2 border-b border-white/10 pb-6">
        <h1 className="text-3xl font-extrabold text-white">DMCA & Copyright Policy</h1>
        <p className="text-xs text-zinc-500">Notice-and-takedown procedure, designated agent, and counter-notification process.</p>
      </div>

      <section className="space-y-3">
        <h2 className="text-lg font-bold text-white">1. Designated Copyright Agent</h2>
        <p>
          clip-it-up respects the intellectual property rights of creators. Under the Digital Millennium Copyright Act (17 U.S.C. § 512) and Rule 75 of the Indian Copyright Rules, notifications of claimed infringement should be sent to our Designated Agent:
        </p>
        <div className="p-3.5 rounded-xl bg-zinc-900 border border-white/10 text-xs text-zinc-400 space-y-1">
          <div>Agent Name: <span className="text-zinc-200">&lt;DESIGNATED_COPYRIGHT_AGENT_NAME&gt;</span></div>
          <div>Company: &lt;COMPANY_LEGAL_NAME&gt;</div>
          <div>Email: <a href="mailto:copyright@clipitup.example.com" className="text-purple-400">copyright@clipitup.example.com</a></div>
          <div>Address: &lt;PHYSICAL_AGENT_ADDRESS&gt;, Karnataka, India</div>
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-bold text-white">2. Repeat Infringer Policy</h2>
        <p>
          In accordance with Section 512(i) of the DMCA, clip-it-up maintains a strict policy of terminating, in appropriate circumstances, user accounts belonging to repeat infringers.
        </p>
      </section>

      {/* 3. Interactive Takedown Intake Form */}
      <section className="space-y-4 pt-4 border-t border-white/10">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <Shield className="w-5 h-5 text-purple-400" />
            <span>Submit a Takedown Notice</span>
          </h2>
          <p className="text-xs text-zinc-400 mt-1">
            Complete this form to notify our legal team of infringing content hosted on clip-it-up.
          </p>
        </div>

        {submitted ? (
          <div className="p-6 rounded-3xl glass-panel-glow border border-emerald-500/40 text-center space-y-3">
            <CheckCircle2 className="w-10 h-10 text-emerald-400 mx-auto" />
            <h3 className="text-lg font-bold text-white">Takedown Request Submitted</h3>
            <p className="text-xs text-zinc-300 max-w-md mx-auto">
              Your takedown notice has been logged under ticket ID{" "}
              <strong className="text-purple-300 font-mono">{submitted.ticket_id}</strong>. The reported media has been quarantined pending review, and an email confirmation was sent to {formData.claimant_email}.
            </p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="glass-panel rounded-3xl p-6 sm:p-8 border border-white/10 space-y-5">
            {error && (
              <div className="p-3.5 rounded-xl bg-red-500/10 border border-red-500/30 text-red-300 text-xs">
                {error}
              </div>
            )}

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1">
                <label className="text-xs font-semibold text-zinc-300">Your Full Name *</label>
                <input
                  type="text"
                  required
                  value={formData.claimant_name}
                  onChange={(e) => setFormData({ ...formData, claimant_name: e.target.value })}
                  placeholder="e.g. Jane Doe"
                  className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-900 border border-white/10 text-xs text-white focus:outline-none focus:border-purple-500"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-zinc-300">Contact Email *</label>
                <input
                  type="email"
                  required
                  value={formData.claimant_email}
                  onChange={(e) => setFormData({ ...formData, claimant_email: e.target.value })}
                  placeholder="jane@example.com"
                  className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-900 border border-white/10 text-xs text-white focus:outline-none focus:border-purple-500"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-zinc-300">Company / Organization (Optional)</label>
                <input
                  type="text"
                  value={formData.claimant_company}
                  onChange={(e) => setFormData({ ...formData, claimant_company: e.target.value })}
                  placeholder="Studio or Agency name"
                  className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-900 border border-white/10 text-xs text-white focus:outline-none focus:border-purple-500"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-zinc-300">Phone Number (Optional)</label>
                <input
                  type="tel"
                  value={formData.claimant_phone}
                  onChange={(e) => setFormData({ ...formData, claimant_phone: e.target.value })}
                  placeholder="+91 98765 43210"
                  className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-900 border border-white/10 text-xs text-white focus:outline-none focus:border-purple-500"
                />
              </div>
            </div>

            <div className="space-y-1">
              <label className="text-xs font-semibold text-zinc-300">Description of Original Work *</label>
              <textarea
                required
                rows={3}
                value={formData.work_description}
                onChange={(e) => setFormData({ ...formData, work_description: e.target.value })}
                placeholder="Identify the copyrighted work claimed to have been infringed (e.g. title, URL to official video, timestamps)..."
                className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-900 border border-white/10 text-xs text-white focus:outline-none focus:border-purple-500"
              />
            </div>

            <div className="space-y-1">
              <label className="text-xs font-semibold text-zinc-300">Infringing Video URLs or Video IDs * (One per line)</label>
              <textarea
                required
                rows={3}
                value={formData.infringing_urls_or_ids}
                onChange={(e) => setFormData({ ...formData, infringing_urls_or_ids: e.target.value })}
                placeholder="https://clipitup.example.com/videos/abc...&#10;or video ID UUID"
                className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-900 border border-white/10 text-xs text-white font-mono focus:outline-none focus:border-purple-500"
              />
            </div>

            <div className="space-y-2 pt-2">
              <label className="flex items-start gap-2.5 text-xs text-zinc-400 cursor-pointer">
                <input
                  type="checkbox"
                  required
                  checked={formData.good_faith_statement}
                  onChange={(e) => setFormData({ ...formData, good_faith_statement: e.target.checked })}
                  className="mt-0.5 rounded border-white/20 bg-zinc-900 text-purple-600 focus:ring-0"
                />
                <span>
                  I have a good faith belief that use of the material in the manner complained of is not authorized by the copyright owner, its agent, or the law.
                </span>
              </label>

              <label className="flex items-start gap-2.5 text-xs text-zinc-400 cursor-pointer">
                <input
                  type="checkbox"
                  required
                  checked={formData.accuracy_statement}
                  onChange={(e) => setFormData({ ...formData, accuracy_statement: e.target.checked })}
                  className="mt-0.5 rounded border-white/20 bg-zinc-900 text-purple-600 focus:ring-0"
                />
                <span>
                  The information in this notification is accurate, and under penalty of perjury, I am the owner or authorized to act on behalf of the owner of an exclusive right that is allegedly infringed.
                </span>
              </label>
            </div>

            <div className="space-y-1">
              <label className="text-xs font-semibold text-zinc-300">Electronic Signature (Type Your Full Legal Name) *</label>
              <input
                type="text"
                required
                value={formData.signature}
                onChange={(e) => setFormData({ ...formData, signature: e.target.value })}
                placeholder="e.g. /Jane Doe/"
                className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-900 border border-white/10 text-xs text-white focus:outline-none focus:border-purple-500"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 py-3 px-4 rounded-xl text-xs font-bold bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white shadow-lg shadow-purple-500/25 active:scale-95 transition-all"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : (
                <>
                  <Send className="w-4 h-4" />
                  <span>Submit DMCA Takedown Notice</span>
                </>
              )}
            </button>
          </form>
        )}
      </section>
    </div>
  );
}
