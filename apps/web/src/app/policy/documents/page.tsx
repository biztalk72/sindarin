import { AppShell } from "@/components/AppShell";
import { AuthGate } from "@/components/AuthGate";
import { DocumentsAclPage } from "@/components/DocumentsAclPage";

export default function DocumentsAclRoute() {
  return (
    <AuthGate>
      <AppShell title="Documents & ACL · 분류 및 권한" active="docs-acl">
        <DocumentsAclPage />
      </AppShell>
    </AuthGate>
  );
}
