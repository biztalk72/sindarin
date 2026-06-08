import { AdminDashboard } from "@/components/AdminDashboard";
import { AuthGate } from "@/components/AuthGate";

// Admin observability (E11). Auth-gated; the admin APIs themselves enforce the admin role
// (403 for non-admins), which AdminDashboard surfaces.
export default function AdminPage() {
  return (
    <AuthGate>
      <AdminDashboard />
    </AuthGate>
  );
}
