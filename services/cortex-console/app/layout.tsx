import type { Metadata } from "next";

import { ConsoleShell } from "@/components/console-shell";
import { Providers } from "@/components/providers";

import "./globals.css";

export const metadata: Metadata = {
  title: "Cortex Console",
  description: "SOC console for Cortex Zero Trust control plane"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <body className="grid-overlay">
        <Providers>
          <ConsoleShell>{children}</ConsoleShell>
        </Providers>
      </body>
    </html>
  );
}
