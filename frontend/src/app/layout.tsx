import type { Metadata, Viewport } from "next";
import "./globals.css";
import "@fontsource-variable/nunito-sans";
import "@fontsource/varela-round";

export const metadata: Metadata = {
  title: "LaTablée",
  description: "Self-hosted recipe & meal planning for the whole table",
  manifest: "manifest.json",
  appleWebApp: { capable: true, statusBarStyle: "default", title: "LaTablée" },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#FAF7F2" },
    { media: "(prefers-color-scheme: dark)", color: "#171412" },
  ],
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        {/* theme before paint — no flash */}
        <script
          dangerouslySetInnerHTML={{
            __html: `try{var t=localStorage.getItem("latablee_theme");if(t)document.documentElement.dataset.theme=t;}catch(e){}`,
          }}
        />
      </head>
      <body>{children}</body>
    </html>
  );
}