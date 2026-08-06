import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--app-font",
});

export const metadata: Metadata = {
  title: "MedIntel AI",
  description: "Evidence-grounded pharmaceutical intelligence",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={inter.variable} style={{ fontFamily: "var(--app-font)" }}>
        {children}
      </body>
    </html>
  );
}