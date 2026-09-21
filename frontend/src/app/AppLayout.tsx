import { AuthGate } from "./AuthGate";
import { SideNav, TabBar } from "./TabBar";
import { ServiceWorker } from "./ServiceWorker";

/**
 * Shell for authed app pages.
 * Mobile: single column + bottom tab bar (pb-24 clears it).
 * Desktop (lg+): sidebar at left; content shifts over (lg:pl-60) and widens
 * (max-w-5xl) for two-column surfaces inside each page.
 */
export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGate>
      <SideNav />
      <div className="mx-auto flex min-h-dvh max-w-xl flex-col px-4 pb-24 pt-6 lg:max-w-5xl lg:pl-64 lg:pr-8 lg:pb-12">
        {children}
      </div>
      <TabBar />
      <ServiceWorker />
    </AuthGate>
  );
}