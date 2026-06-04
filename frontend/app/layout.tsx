import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Financial AI Agent",
  description: "Multi-agent market insights with streamed research reports"
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

