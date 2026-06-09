import { AppShell } from "@/components/AppShell";
import { AuthGate } from "@/components/AuthGate";
import { DsrPage } from "@/components/DsrPage";

export default function DsrRoute() {
  return (
    <AuthGate>
      <AppShell title="Data Subject Requests · 정보주체 요청" active="dsr">
        <DsrPage />
      </AppShell>
    </AuthGate>
  );
}
