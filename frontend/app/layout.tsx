import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ClinicalSafe NIM",
  description: "NVIDIA NIM-powered clinical summarization platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased min-h-screen bg-clinical text-parchment">
        {children}
      </body>
    </html>
  );
}
