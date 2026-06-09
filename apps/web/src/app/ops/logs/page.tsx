import { ActivityLogs } from "@/components/ActivityLogs";
import { AppShell } from "@/components/AppShell";
import { AuthGate } from "@/components/AuthGate";

export default function OpsLogsPage() {
  return (
    <AuthGate>
      <AppShell title="Activity Logs · 활동 로그" active="logs">
        <ActivityLogs />
      </AppShell>
    </AuthGate>
  );
}
