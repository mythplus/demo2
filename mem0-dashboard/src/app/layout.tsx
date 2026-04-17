import React from "react";
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { ClientLayout } from "@/components/layout/client-layout";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], display: "swap" });

export const metadata: Metadata = {
  title: {
    default: "Mem0 Dashboard",
    template: "%s | Mem0 Dashboard",
  },
  description: "Mem0 记忆管理后台 — 管理、搜索、分析 AI 记忆数据",
  icons: {
    icon: "/favicon.ico",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // 阻塞式主题初始化脚本：在浏览器第一帧渲染前同步读取 localStorage，
  // 立即设置 dark class，避免"先浅色再闪回深色"的 FOUC 问题
  const themeInitScript = `
    (function() {
      try {
        var saved = localStorage.getItem('mem0-preferences');
        if (saved) {
          var prefs = JSON.parse(saved);
          if (prefs.themeMode === 'dark') {
            document.documentElement.classList.add('dark');
          }
        }
      } catch(e) {}
    })();
  `;

  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body className={inter.className} suppressHydrationWarning>
        <ClientLayout>{children}</ClientLayout>
      </body>
    </html>
  );
}
