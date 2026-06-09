import { AdminDashboard } from "@/components/AdminDashboard";
import { AppShell } from "@/components/AppShell";
import { AuthGate } from "@/components/AuthGate";

// Admin observability (E11). Auth-gated; the admin APIs themselves enforce the admin role
// (403 for non-admins), which AdminDashboard surfaces.
export default function AdminPage() {
  return (
    <AuthGate>
      <AppShell title="Admin · 관찰성" active="admin">
        <AdminDashboard />
      </AppShell>
    </AuthGate>
  );
}
