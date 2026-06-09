import { Poppins } from "next/font/google";
import type { ReactNode } from "react";

import "bootstrap/dist/css/bootstrap.min.css";
import "shards-ui/dist/css/shards.min.css";
import "./globals.css";

const poppins = Poppins({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-poppins",
  display: "swap",
});

export const metadata = {
  title: "Hybrid IDP",
  description: "Self-hosted document AI workspace",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ko" className={poppins.variable}>
      <body className={poppins.className}>{children}</body>
    </html>
  );
}
