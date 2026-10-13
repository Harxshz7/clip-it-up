import { Shield, AlertCircle, Lock, Eye, Trash2, Download } from "lucide-react";

export const metadata = {
  title: "Privacy Policy | clip-it-up",
  description: "Privacy policy and DPDP Act 2023 compliance notes for clip-it-up.",
};

export default function PrivacyPage() {
  return (
    <div className="max-w-4xl mx-auto py-10 space-y-8 text-zinc-300 text-sm leading-relaxed">
      {/* Notice Banner */}
      <div className="p-4 rounded-2xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs flex items-center gap-3">
        <AlertCircle className="w-5 h-5 shrink-0" />
        <div>
          <strong>DRAFT - REQUIRES FORMAL LEGAL REVIEW:</strong> This privacy policy is drafted in alignment with India's Digital Personal Data Protection Act, 2023 (DPDP Act) and international data protection standards.
        </div>
      </div>

      <div className="space-y-2 border-b border-white/10 pb-6">
        <h1 className="text-3xl font-extrabold text-white">Privacy Policy</h1>
        <p className="text-xs text-zinc-500">Version 1.0 • Effective Date: October 13, 2026</p>
      </div>

      <section className="space-y-3">
        <h2 className="text-lg font-bold text-white">1. Data Principal Principles & DPDP Act 2023 Alignment</h2>
        <p>
          clip-it-up acts as a Data Fiduciary under the Digital Personal Data Protection Act, 2023. We collect and process digital personal data only for lawful purposes for which you have provided explicit, informed, and unambiguous consent.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-bold text-white">2. Information We Collect</h2>
        <ul className="list-disc pl-5 space-y-1.5 text-zinc-400">
          <li><strong>Account Data:</strong> Email address, name, authentication identifiers via Clerk.</li>
          <li><strong>Media Data:</strong> Video files, extracted audio tracks, generated transcripts, crop coordinates, and rendered clips uploaded or produced by you.</li>
          <li><strong>Billing Data:</strong> Billing address, GSTIN (for Indian businesses), and transaction IDs via Razorpay and Stripe. We do NOT store complete credit card or UPI details on our servers.</li>
          <li><strong>Technical Data:</strong> IP address hashes, browser user-agent, session telemetry, and error logs (via Sentry with PII masking).</li>
        </ul>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-bold text-white">3. Data Principal Rights</h2>
        <p>Under the DPDP Act 2023 and global standards, you have the following rights:</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
          <div className="p-3.5 rounded-xl bg-zinc-900 border border-white/10 space-y-1">
            <h4 className="text-xs font-bold text-white flex items-center gap-1.5">
              <Download className="w-3.5 h-3.5 text-purple-400" /> Right to Access & Portability
            </h4>
            <p className="text-[11px] text-zinc-400">
              Download all your account data, projects, transcripts, and metadata via the "Download my data" feature.
            </p>
          </div>

          <div className="p-3.5 rounded-xl bg-zinc-900 border border-white/10 space-y-1">
            <h4 className="text-xs font-bold text-white flex items-center gap-1.5">
              <Trash2 className="w-3.5 h-3.5 text-red-400" /> Right to Erasure & Deletion
            </h4>
            <p className="text-[11px] text-zinc-400">
              Trigger hard deletion of specific videos or complete account purge with verifiable audit logging.
            </p>
          </div>
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-bold text-white">4. Cookies and Tracking</h2>
        <p>
          We use strictly necessary cookies for authentication and session management. We honor Do-Not-Track (DNT) browser signals and do not use third-party cross-site advertising tracking cookies.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-bold text-white">5. Security Measures</h2>
        <p>
          Data is protected using industry-standard TLS 1.3 encryption in transit and AES-256 encryption at rest on S3-compatible cloud storage. Database credentials and API secrets are strictly managed via environment variables and never logged.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-bold text-white">6. Grievance Officer & Contact</h2>
        <p>
          For privacy inquiries, consent withdrawal, or data principal requests:
        </p>
        <div className="p-3 rounded-xl bg-zinc-900 border border-white/10 text-xs text-zinc-400 space-y-1">
          <div>Grievance Officer: <span className="text-zinc-200">&lt;GRIEVANCE_OFFICER_NAME&gt;</span></div>
          <div>Email: <a href="mailto:privacy@clipitup.example.com" className="text-purple-400">privacy@clipitup.example.com</a></div>
          <div>Jurisdiction: Karnataka, India</div>
        </div>
      </section>
    </div>
  );
}
