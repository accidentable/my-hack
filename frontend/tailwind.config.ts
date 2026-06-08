import type { Config } from "tailwindcss";

/**
 * 디자인 토큰 — 토스 풍 B2B 업무 도구.
 *
 * 원칙:
 *  - 무채색(white / ink / muted / line) 베이스 + 포인트는 brand 블루 1개
 *  - 의미 있는 색은 심각도(sev.*)에만 사용
 *  - 라운드는 잔잔히, 그림자는 거의 안 씀
 */
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          "Pretendard",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
      },
      colors: {
        // 무채색 베이스
        page: "#ffffff",
        ink: "#0f172a",        // 본문/제목
        muted: "#64748b",      // 보조 텍스트 (slate-500)
        soft: "#94a3b8",       // 더 옅은 보조 (slate-400)
        line: "#e2e8f0",       // 구분선 (slate-200)
        bg: "#f8fafc",         // 섹션 배경 (slate-50)
        // 포인트 컬러 — 단 하나의 브랜드 블루
        brand: {
          DEFAULT: "#1d4ed8",  // blue-700, 차분
          hover: "#1e40af",    // blue-800
          weak: "#eff6ff",     // blue-50, 배경용 (드물게)
        },
        // 심각도 — 차분한 톤
        sev: {
          high: "#dc2626",     // red-600
          medium: "#d97706",   // amber-600
          low: "#64748b",      // slate-500
          pass: "#059669",     // emerald-600
        },
      },
      fontSize: {
        // 본문 기본 14~16, 위계는 굵기·크기로
        xs: ["12px", "18px"],
        sm: ["14px", "22px"],
        base: ["15px", "24px"],
        lg: ["17px", "26px"],
        xl: ["20px", "30px"],
        "2xl": ["24px", "34px"],
        "3xl": ["30px", "40px"],
      },
      borderRadius: {
        sm: "4px",
        DEFAULT: "8px",
        md: "10px",
        lg: "12px",
      },
    },
  },
  plugins: [],
};
export default config;
