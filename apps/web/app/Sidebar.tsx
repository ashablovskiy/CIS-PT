"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

const NAV = [
  { href: "/CIS-PT/",             label: "Daily Brief",    icon: "📋" },
  { href: "/CIS-PT/network",      label: "Network State",  icon: "🕸️" },
  { href: "/CIS-PT/signals",      label: "Signals",        icon: "📡" },
  { href: "/CIS-PT/assessments",  label: "Assessments",    icon: "🔍" },
  { href: "/CIS-PT/agents",       label: "Agents",         icon: "⚙️" },
  { href: "/CIS-PT/admin/prompts",label: "Prompts",        icon: "✏️" },
];

export default function Sidebar() {
  const pathname  = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const [mounted,   setMounted]   = useState(false);

  // Read persisted state after mount (avoid SSR mismatch)
  useEffect(() => {
    setMounted(true);
    try {
      const saved = localStorage.getItem("cis-sidebar-collapsed");
      if (saved !== null) setCollapsed(saved === "true");
    } catch {}
  }, []);

  function toggle() {
    setCollapsed((prev) => {
      const next = !prev;
      try { localStorage.setItem("cis-sidebar-collapsed", String(next)); } catch {}
      return next;
    });
  }

  // Suppress hydration mismatch by rendering expanded on server
  const isCollapsed = mounted && collapsed;

  return (
    <aside
      className={`shrink-0 bg-slate-900 text-slate-300 flex flex-col min-h-screen transition-all duration-200
        ${isCollapsed ? "w-14" : "w-56"}`}
    >
      {/* Header */}
      <div className={`border-b border-slate-700 flex items-center
        ${isCollapsed ? "px-3 py-4 justify-center" : "px-5 py-5 justify-between"}`}>
        {!isCollapsed && (
          <div>
            <div className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-1">CIS</div>
            <div className="text-sm font-medium text-white leading-tight">Contract Intelligence</div>
          </div>
        )}
        <button
          onClick={toggle}
          title={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          className="text-slate-500 hover:text-slate-200 transition-colors p-1 rounded"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
            {isCollapsed ? (
              // chevron right (expand)
              <path d="M5.7 3.3a1 1 0 0 1 1.4 0l4 4a1 1 0 0 1 0 1.4l-4 4a1 1 0 1 1-1.4-1.4L9 8 5.7 4.7a1 1 0 0 1 0-1.4z"/>
            ) : (
              // chevron left (collapse)
              <path d="M10.3 3.3a1 1 0 0 1 0 1.4L7 8l3.3 3.3a1 1 0 1 1-1.4 1.4l-4-4a1 1 0 0 1 0-1.4l4-4a1 1 0 0 1 1.4 0z"/>
            )}
          </svg>
        </button>
      </div>

      {/* Nav links */}
      <nav className={`flex-1 py-4 space-y-1 ${isCollapsed ? "px-1.5" : "px-3"}`}>
        {NAV.map(({ href, label, icon }) => {
          // Active detection — strip /CIS-PT prefix for comparison
          const active = pathname === href || pathname.startsWith(href + "/");
          return (
            <Link
              key={href}
              href={href}
              title={isCollapsed ? label : undefined}
              className={`flex items-center rounded-lg text-sm transition-colors
                ${isCollapsed ? "justify-center px-2 py-2.5" : "gap-3 px-3 py-2"}
                ${active
                  ? "bg-slate-700 text-white"
                  : "hover:bg-slate-800 hover:text-white"}`}
            >
              <span className="text-base leading-none shrink-0">{icon}</span>
              {!isCollapsed && <span>{label}</span>}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      {!isCollapsed && (
        <div className="px-5 py-4 border-t border-slate-700 text-xs text-slate-600">
          v0.8.0 — Week 8
        </div>
      )}
    </aside>
  );
}
