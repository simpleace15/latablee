import { AuthGate } from "./AuthGate";
import { TabBar } from "./TabBar";
import { ServiceWorker } from "./ServiceWorker";

/** Shell for authed app pages: tab bar + content area. */
export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGate>
      <div className="mx-auto flex min-h-dvh max-w-xl flex-col px-4 pb-24 pt-6">
        {children}
      </div>
      <TabBar />
      <ServiceWorker />
    </AuthGate>
  );
}