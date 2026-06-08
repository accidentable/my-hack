import type { Metadata } from "next";
import "./globals.css";
import { ThreadHistoryTabs } from "@/components/ThreadHistoryTabs";

export const metadata: Metadata = {
  title: "ComplianceLens",
  description: "멀티모달·다국어 금융 콘텐츠 사전심의 AI Agent",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body className="bg-page text-ink font-sans antialiased">
        <header className="border-b border-line bg-page">
          <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-6">
            <a href="/" className="text-base font-semibold tracking-tight">
              ComplianceLens
            </a>
            <span className="text-sm text-muted">준법심의 보조 AI</span>
          </div>
          {/* 이전 심의 thread 히스토리 — 항상 헤더 아래에 탭처럼 노출 */}
          <div className="mx-auto max-w-6xl px-6">
            <ThreadHistoryTabs />
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-6 py-10">{children}</main>
        <footer className="mx-auto max-w-6xl px-6 py-10 text-xs text-soft">
          JB금융그룹 Fin:AI Challenge · 데모용. 최종 결정은 사람 준법관리자가 합니다.
        </footer>
      </body>
    </html>
  );
}
