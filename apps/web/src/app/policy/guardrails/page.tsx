import { AppShell } from "@/components/AppShell";
import { AuthGate } from "@/components/AuthGate";
import { GuardrailsPage } from "@/components/GuardrailsPage";

export default function GuardrailsRoute() {
  return (
    <AuthGate>
      <AppShell title="Guardrails · 안전" active="guardrails">
        <GuardrailsPage />
      </AppShell>
    </AuthGate>
  );
}
