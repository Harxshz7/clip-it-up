import type { Metadata } from "next";
import "./globals.css";
import { Navbar } from "@/components/Navbar";
import { UploadModal } from "@/components/UploadModal";

export const metadata: Metadata = {
  title: "clip-it-up | Turn Long Videos Into Viral Shorts",
  description: "High-performance video clipping SaaS pipeline powered by FastAPI, Celery, and Next.js.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen flex flex-col bg-[#07090e] text-zinc-100 antialiased selection:bg-purple-500 selection:text-white">
        <Navbar />
        <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
          {children}
        </main>
        <UploadModal />
      </body>
    </html>
  );
}
