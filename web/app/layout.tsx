import type { Metadata } from "next";
import { Atkinson_Hyperlegible_Next, Big_Shoulders, Tiro_Devanagari_Hindi } from "next/font/google";
import "./globals.css";

const display = Big_Shoulders({ subsets: ["latin"], weight: ["500", "700", "900"], variable: "--font-display" });
const body = Atkinson_Hyperlegible_Next({ subsets: ["latin"], variable: "--font-body" });
const deva = Tiro_Devanagari_Hindi({ subsets: ["devanagari", "latin"], weight: "400", variable: "--font-deva" });

export const metadata: Metadata = {
  title: "Tiffin relay estimator · Bhopal Dabba Relay Union",
  description: "When will lunch reach the office desk? Estimates for every tiffin relay batch, with a Hindi, Hinglish and English assistant.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${display.variable} ${body.variable} ${deva.variable}`}>
      <body>{children}</body>
    </html>
  );
}
