"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { isDemo } from "@/lib/api";

const NAV = [
  { href: "/", label: "Review queue" },
  { href: "/ops", label: "Operations" },
  { href: "/about", label: "How it works" },
];

export default function Header() {
  const path = usePathname();
  return (
    <header className="border-b border-zinc-200 bg-white">
      <div className="mx-auto flex h-14 max-w-7xl items-center gap-3 px-4 sm:gap-6 sm:px-6">
        <Link
          href="/"
          className="shrink-0 whitespace-nowrap rounded font-semibold tracking-tight text-zinc-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
        >
          Borrower Truth
        </Link>
        <nav className="-mx-1 flex min-w-0 gap-1 overflow-x-auto px-1 whitespace-nowrap" aria-label="Main">
          {NAV.map((n) => {
            const active = n.href === "/" ? path === "/" || path.startsWith("/case") : path.startsWith(n.href);
            return (
              <Link
                key={n.href}
                href={n.href}
                aria-current={active ? "page" : undefined}
                className={`rounded-md px-3 py-1.5 text-sm transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 ${
                  active ? "bg-zinc-100 font-medium text-zinc-900" : "text-zinc-600 hover:bg-zinc-50 hover:text-zinc-900"
                }`}
              >
                {n.label}
              </Link>
            );
          })}
        </nav>
        <span className="ml-auto hidden text-xs text-zinc-500 sm:block">
          {isDemo ? "Demo mode · static snapshot, decisions stay in your browser" : "Live · connected to the case service"}
        </span>
      </div>
    </header>
  );
}
