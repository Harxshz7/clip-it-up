import { ShieldAlert, AlertCircle } from "lucide-react";

export const metadata = {
  title: "Acceptable Use Policy | clip-it-up",
  description: "Acceptable use guidelines, platform caps, and prohibited content rules.",
};

export default function AupPage() {
  return (
    <div className="max-w-4xl mx-auto py-10 space-y-8 text-zinc-300 text-sm leading-relaxed">
      {/* Notice Banner */}
      <div className="p-4 rounded-2xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs flex items-center gap-3">
        <AlertCircle className="w-5 h-5 shrink-0" />
        <div>
          <strong>DRAFT - REQUIRES FORMAL LEGAL REVIEW:</strong> Platform acceptable use and content safety baseline.
        </div>
      </div>

      <div className="space-y-2 border-b border-white/10 pb-6">
        <h1 className="text-3xl font-extrabold text-white">Acceptable Use Policy</h1>
        <p className="text-xs text-zinc-500">Version 1.0 • Effective Date: October 13, 2026</p>
      </div>

      <section className="space-y-3">
        <h2 className="text-lg font-bold text-white">1. Prohibited Activities</h2>
        <p>You agree not to use clip-it-up to upload, process, or render any media that contains:</p>
        <ul className="list-disc pl-5 space-y-1.5 text-zinc-400">
          <li>Child Sexual Abuse Material (CSAM) or any form of child exploitation (reported immediately to law enforcement).</li>
          <li>Content that incites imminent violence, terrorism, or illegal acts under applicable Indian or international law.</li>
          <li>Unconsented intimate imagery, non-consensual deepfakes, or harassment.</li>
          <li>Infringing audio or video for which you do not have appropriate license or fair use authorization.</li>
          <li>Malware, viruses, corrupted payloads, or automated bot scraping targeting our infrastructure.</li>
        </ul>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-bold text-white">2. Rate Limits & Technical Caps</h2>
        <p>
          To ensure platform stability and protect system resources for all creators, we enforce server-side rate limits and caps:
        </p>
        <ul className="list-disc pl-5 space-y-1.5 text-zinc-400">
          <li><strong>Upload Limits:</strong> Maximum file size up to 200MB (Free) or 2GB (Paid), maximum video length 120 minutes.</li>
          <li><strong>Concurrency Caps:</strong> Maximum 1 concurrent processing job on Free, 2 on Creator, 4 on Pro.</li>
          <li><strong>API Rate Limits:</strong> Token bucket rate limiters are active on all public and authenticated endpoints. Exceeding limits returns HTTP 429 with a <code>Retry-After</code> header.</li>
          <li><strong>Free Tier Abuse Cap:</strong> Maximum 3 free signups per IP address per day. Disposable temporary email domains are rejected at registration.</li>
        </ul>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-bold text-white">3. Enforcement & Suspension</h2>
        <p>
          clip-it-up reserves the right to suspend or terminate accounts, block videos, or revoke access immediately without prior notice upon detection of egregious AUP violations. Repeated copyright infringement or terms violations will result in permanent banning of user accounts and associated domains.
        </p>
      </section>
    </div>
  );
}
