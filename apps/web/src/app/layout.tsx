import type { ReactNode } from "react";

import "./globals.css";

export const metadata = {
  title: "Hybrid IDP",
  description: "Self-hosted document AI workspace",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
