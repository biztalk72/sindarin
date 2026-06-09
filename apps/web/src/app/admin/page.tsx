import { redirect } from "next/navigation";

// IA v2 moved the admin console to /ops/health. Bookmarks land here briefly until the
// next minor that drops the route entirely.
export default function AdminLegacyRedirect(): never {
  redirect("/ops/health");
}
