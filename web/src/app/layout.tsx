import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Header from "@/components/Header";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Borrower Truth · review console",
  description:
    "Seven connected checks that answer one question: is this borrower's picture of itself true? Synthetic demo data.",
  robots: { index: false, follow: false }, // shared by link, not listed in search engines
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col">
        <div className="border-b border-amber-200 bg-amber-50 px-4 py-1.5 text-center text-xs text-amber-900">
          All data is synthetic. No real company, person or loan is shown. An internship-application project, not
          affiliated with Wells Fargo.
        </div>
        <Header />
        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-8 sm:px-6">{children}</main>
        <footer className="space-y-1 border-t border-zinc-200 px-4 py-6 text-center text-xs text-zinc-500">
          <p>Borrower Truth · every finding links to its evidence · a human approves every action</p>
          <p>
            © 2026 Vedant Tigade. A demonstration only, not for reuse. The code, the full dataset, the rules and the model
            weights are private and not part of this site.
          </p>
        </footer>
      </body>
    </html>
  );
}
