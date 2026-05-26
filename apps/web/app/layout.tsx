import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "CIS — Contract Intelligence System",
  description: "Power transformer procurement intelligence",
};

const NAV = [
  { href: "/", label: "Daily Brief", icon: "📋" },
  { href: "/signals", label: "Signals", icon: "📡" },
  { href: "/assessments", label: "Assessments", icon: "🔍" },
  { href: "/agents", label: "Agents", icon: "⚙️" },
  { href: "/admin/prompts", label: "Prompts", icon: "✏️" },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full`}>
      <body className="min-h-full flex">
        {/* Sidebar */}
        <aside className="w-56 shrink-0 bg-slate-900 text-slate-300 flex flex-col min-h-screen">
          <div className="px-5 py-5 border-b border-slate-700">
            <div className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-1">
              CIS
            </div>
            <div className="text-sm font-medium text-white leading-tight">
              Contract Intelligence
            </div>
          </div>
          <nav className="flex-1 px-3 py-4 space-y-1">
            {NAV.map(({ href, label, icon }) => (
              <Link
                key={href}
                href={href}
                className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors hover:bg-slate-800 hover:text-white"
              >
                <span className="text-base leading-none">{icon}</span>
                {label}
              </Link>
            ))}
          </nav>
          <div className="px-5 py-4 border-t border-slate-700 text-xs text-slate-600">
            v0.8.0 — Week 8
          </div>
        </aside>

        {/* Main content */}
        <main className="flex-1 min-w-0 overflow-auto">
          {children}
        </main>
      </body>
    </html>
  );
}
