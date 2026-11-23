import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { ThemeProvider } from "@/components/theme-provider";
import { Sidebar } from "@/components/layout/sidebar";
import { Header } from "@/components/layout/header";
import { Toaster } from "sonner";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "LectureForge AI - AI Lecture Notes to Study Pack Engine",
  description:
    "Transform lecture notes, textbook chapters, and slide presentations into comprehensive active recall study packs with verified citations.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={inter.className}>
        <ThemeProvider
          attribute="class"
          defaultTheme="system"
          enableSystem
          disableTransitionOnChange
        >
          <div className="flex min-h-screen bg-background">
            {/* Sidebar navigation */}
            <Sidebar />

            {/* Main content viewport */}
            <div className="flex flex-1 flex-col overflow-hidden">
              <Header />
              <main className="flex-1 overflow-y-auto px-4 py-6 sm:px-8 sm:py-8">
                <div className="mx-auto max-w-7xl">{children}</div>
              </main>
            </div>
          </div>

          {/* Toast notifications */}
          <Toaster richColors position="top-right" closeButton />
        </ThemeProvider>
      </body>
    </html>
  );
}
