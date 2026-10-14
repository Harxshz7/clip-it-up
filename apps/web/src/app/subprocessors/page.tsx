import { Server, ShieldCheck, AlertCircle } from "lucide-react";

export const metadata = {
  title: "Subprocessors List | clip-it-up",
  description: "Third-party vendors and cloud subprocessors engaged by clip-it-up.",
};

export default function SubprocessorsPage() {
  const subprocessors = [
    {
      name: "Clerk",
      purpose: "User authentication, identity verification, session management",
      location: "United States",
      security: "SOC 2 Type II, ISO 27001",
    },
    {
      name: "Razorpay Software Pvt Ltd",
      purpose: "Payment processing, INR subscriptions, GST invoicing, UPI integration",
      location: "India",
      security: "PCI-DSS Level 1, ISO 27001",
    },
    {
      name: "Stripe, Inc.",
      purpose: "International payment gateway, multi-currency card processing",
      location: "United States",
      security: "PCI-DSS Level 1",
    },
    {
      name: "Amazon Web Services (AWS) / MinIO",
      purpose: "S3-compatible encrypted cloud storage for video chunks and exports",
      location: "India / US",
      security: "SOC 1/2/3, ISO 27001, HIPAA compliant",
    },
    {
      name: "Modal Labs / RunPod",
      purpose: "Serverless GPU inference execution for Whisper transcription and FFmpeg rendering",
      location: "United States",
      security: "Enterprise cloud security, isolated worker containers",
    },
    {
      name: "Google Cloud / OpenAI / Groq",
      purpose: "LLM semantic scoring of video clips and hook quality ranking",
      location: "United States",
      security: "Enterprise zero-retention API contracts",
    },
    {
      name: "Resend / Amazon SES",
      purpose: "Transactional email delivery (invoices, receipt PDFs, system notifications)",
      location: "United States",
      security: "SOC 2 Type II, DKIM / SPF / DMARC",
    },
    {
      name: "Functional Software (Sentry)",
      purpose: "Application error tracking, release diagnostics with automated PII masking",
      location: "United States",
      security: "SOC 2 Type II",
    },
  ];

  return (
    <div className="max-w-4xl mx-auto py-10 space-y-8 text-zinc-300 text-sm leading-relaxed">
      {/* Notice Banner */}
      <div className="p-4 rounded-2xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs flex items-center gap-3">
        <AlertCircle className="w-5 h-5 shrink-0" />
        <div>
          <strong>DRAFT - REQUIRES FORMAL LEGAL REVIEW:</strong> List of approved third-party subprocessors under DPDP Act 2023 and GDPR guidelines.
        </div>
      </div>

      <div className="space-y-2 border-b border-white/10 pb-6">
        <h1 className="text-3xl font-extrabold text-white">Subprocessors & Vendors</h1>
        <p className="text-xs text-zinc-500">Updated: October 13, 2026 • Version 1.0</p>
      </div>

      <p className="text-zinc-400">
        To deliver our distributed media processing services, clip-it-up engages third-party infrastructure and software service providers ("Subprocessors"). Each subprocessor is vetted for rigorous data protection standards and bound by contractual data processing agreements.
      </p>

      <div className="glass-panel rounded-3xl border border-white/10 overflow-hidden">
        <table className="w-full text-left text-xs text-zinc-300">
          <thead className="bg-white/[0.03] text-zinc-400 uppercase text-[10px] tracking-wider border-b border-white/5">
            <tr>
              <th className="px-5 py-3">Subprocessor</th>
              <th className="px-5 py-3">Service Provided</th>
              <th className="px-5 py-3">Data Location</th>
              <th className="px-5 py-3">Security Standards</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {subprocessors.map((sub, idx) => (
              <tr key={idx} className="hover:bg-white/[0.02] transition-colors">
                <td className="px-5 py-3.5 font-bold text-white">{sub.name}</td>
                <td className="px-5 py-3.5 text-zinc-400">{sub.purpose}</td>
                <td className="px-5 py-3.5">{sub.location}</td>
                <td className="px-5 py-3.5 text-zinc-400">{sub.security}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
