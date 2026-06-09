import { AppShell } from "@/components/AppShell";
import { AuthGate } from "@/components/AuthGate";
import { CompliancePage } from "@/components/CompliancePage";

export default function ComplianceRoute() {
  return (
    <AuthGate>
      <AppShell title="Compliance Report · 컴플라이언스" active="compliance">
        <CompliancePage />
      </AppShell>
    </AuthGate>
  );
}
