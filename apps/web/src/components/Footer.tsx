"use client";

import Link from "next/link";
import { Scissors, Shield, Heart } from "lucide-react";

export function Footer() {
  return (
    <footer className="border-t border-white/10 bg-[#06080d] py-12 text-zinc-400 text-xs">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-8">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
          {/* Brand */}
          <div className="space-y-3">
            <Link href="/" className="flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-tr from-purple-600 to-indigo-500 text-white">
                <Scissors className="h-4 w-4" />
              </div>
              <span className="font-bold text-base text-white tracking-tight">
                clip<span className="text-purple-400">it</span>up
              </span>
            </Link>
            <p className="text-zinc-500 text-[11px] leading-relaxed">
              Automated AI clipping and smart reframing engine for video creators, podcasters, and media teams.
            </p>
            <div className="flex items-center gap-1.5 text-[11px] text-zinc-500">
              <Shield className="w-3.5 h-3.5 text-purple-400" />
              <span>Compliant with DPDP Act 2023</span>
            </div>
          </div>

          {/* Product */}
          <div className="space-y-2.5">
            <h4 className="text-zinc-200 font-semibold uppercase tracking-wider text-[11px]">Product</h4>
            <ul className="space-y-2 text-zinc-400">
              <li>
                <Link href="/dashboard" className="hover:text-white transition-colors">
                  Dashboard
                </Link>
              </li>
              <li>
                <Link href="/videos/00000000-0000-0000-0000-000000000099/clips" className="hover:text-white transition-colors">
                  Interactive Sample Project
                </Link>
              </li>
              <li>
                <Link href="/settings/billing" className="hover:text-white transition-colors">
                  Pricing & Billing
                </Link>
              </li>
              <li>
                <Link href="/admin" className="hover:text-white transition-colors">
                  Admin Analytics
                </Link>
              </li>
            </ul>
          </div>

          {/* Legal & Compliance */}
          <div className="space-y-2.5">
            <h4 className="text-zinc-200 font-semibold uppercase tracking-wider text-[11px]">Legal & Trust</h4>
            <ul className="space-y-2 text-zinc-400">
              <li>
                <Link href="/terms" className="hover:text-white transition-colors">
                  Terms of Service
                </Link>
              </li>
              <li>
                <Link href="/privacy" className="hover:text-white transition-colors">
                  Privacy Policy
                </Link>
              </li>
              <li>
                <Link href="/aup" className="hover:text-white transition-colors">
                  Acceptable Use Policy
                </Link>
              </li>
              <li>
                <Link href="/refund" className="hover:text-white transition-colors">
                  Refund & Cancellation
                </Link>
              </li>
              <li>
                <Link href="/copyright" className="hover:text-white transition-colors">
                  DMCA & Copyright Policy
                </Link>
              </li>
              <li>
                <Link href="/subprocessors" className="hover:text-white transition-colors">
                  Subprocessors List
                </Link>
              </li>
            </ul>
          </div>

          {/* Support & Contact */}
          <div className="space-y-2.5">
            <h4 className="text-zinc-200 font-semibold uppercase tracking-wider text-[11px]">Support & Grievance</h4>
            <p className="text-zinc-500 text-[11px] leading-relaxed">
              Questions regarding billing, takedowns, or data erasure? Contact our team.
            </p>
            <div className="space-y-1 text-zinc-400 text-[11px]">
              <div>Email: <a href="mailto:support@clipitup.example.com" className="text-purple-400 hover:underline">support@clipitup.example.com</a></div>
              <div>Grievance Officer: <span className="text-zinc-300">&lt;GRIEVANCE_OFFICER_NAME&gt;</span></div>
              <div className="text-zinc-500">Karnataka, India</div>
            </div>
          </div>
        </div>

        <div className="border-t border-white/5 pt-6 flex flex-col sm:flex-row items-center justify-between gap-4 text-[11px] text-zinc-500">
          <div>
            © {new Date().getFullYear()} clip-it-up Technologies. All rights reserved. Prices exclude GST where applicable.
          </div>
          <div className="flex items-center gap-1">
            <span>Crafted for creators in India and worldwide</span>
          </div>
        </div>
      </div>
    </footer>
  );
}
