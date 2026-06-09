import { AdminDashboard } from "@/components/AdminDashboard";
import { AppShell } from "@/components/AppShell";
import { AuthGate } from "@/components/AuthGate";

// /ops/health · Health & Metrics — admin/auditor read.
// AdminDashboard kept its name even though its IA location moved; the component itself is
// unchanged. Phase 2 may rename it for clarity, but coupling to the test suite (admin only
// role gate) is preserved here.
export default function OpsHealthPage() {
  return (
    <AuthGate>
      <AppShell title="Health & Metrics · 관찰성" active="health">
        <AdminDashboard />
      </AppShell>
    </AuthGate>
  );
}
