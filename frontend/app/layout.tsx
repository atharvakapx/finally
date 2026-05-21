import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { MarketDataProvider } from "@/hooks/useMarketData";
import { TradingStoreProvider } from "@/hooks/useTradingStore";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "FinAlly — AI Trading Workstation",
  description: "AI-powered trading workstation with live market data",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <MarketDataProvider>
          <TradingStoreProvider>{children}</TradingStoreProvider>
        </MarketDataProvider>
      </body>
    </html>
  );
}
