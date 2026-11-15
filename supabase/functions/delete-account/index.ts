// Edge function: erase the caller's data, then remove their login.
// NOT DEPLOYED AND NOT RUN. Written against the Supabase Edge runtime (Deno); verify before use.
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

Deno.serve(async (req) => {
  if (req.method !== "POST") return new Response("method not allowed", { status: 405 });
  const auth = req.headers.get("Authorization") ?? "";
  const url = Deno.env.get("SUPABASE_URL")!;
  // Act as the caller first, so row-level security decides what can be deleted.
  const asUser = createClient(url, Deno.env.get("SUPABASE_ANON_KEY")!, { global: { headers: { Authorization: auth } } });
  const { data: { user }, error } = await asUser.auth.getUser();
  if (error || !user) return new Response("unauthorized", { status: 401 });
  const wiped = await asUser.rpc("delete_my_data");
  if (wiped.error) return new Response("could not erase data", { status: 500 });
  // Only now use the service role, and only for this one user id.
  const admin = createClient(url, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);
  const gone = await admin.auth.admin.deleteUser(user.id);
  if (gone.error) return new Response("data erased; login removal failed, retry", { status: 500 });
  return new Response(null, { status: 204 });
});
