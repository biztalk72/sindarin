import { AppShell } from "@/components/AppShell";
import { AuditTrail } from "@/components/AuditTrail";
import { AuthGate } from "@/components/AuthGate";

export default function AuditTrailPage() {
  return (
    <AuthGate>
      <AppShell title="Audit Trail · 감사 추적" active="audit">
        <AuditTrail />
      </AppShell>
    </AuthGate>
  );
}
