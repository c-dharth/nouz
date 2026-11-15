// Edge function: verify a purchase with Apple or Google, then write the entitlement row.
// NOT DEPLOYED AND NOT RUN. The two store calls are left as explicit stubs: they need App Store Connect and
// Google Play credentials that do not exist yet. Until they are filled in, this function refuses every request,
// so nobody can be granted Plus by a receipt that was not checked.
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

type Verified = { productId: string; status: "active" | "grace" | "expired" | "revoked" | "refunded"; environment: "production" | "sandbox";
  expiresAt: number; graceUntil?: number; willRenew: boolean; originalTransactionId: string };

// Apple: validate the signed transaction (JWS) from StoreKit 2 against Apple's certificate chain, or call the App Store Server API.
async function verifyApple(_signedTransaction: string): Promise<Verified | null> { return null; /* TODO: needs App Store Connect key */ }
// Google: call purchases.subscriptionsv2.get with a service account.
async function verifyGoogle(_purchaseToken: string): Promise<Verified | null> { return null; /* TODO: needs Play service account */ }

Deno.serve(async (req) => {
  const url = Deno.env.get("SUPABASE_URL")!;
  const asUser = createClient(url, Deno.env.get("SUPABASE_ANON_KEY")!, { global: { headers: { Authorization: req.headers.get("Authorization") ?? "" } } });
  const { data: { user } } = await asUser.auth.getUser();
  if (!user) return new Response("unauthorized", { status: 401 });
  const body = await req.json().catch(() => ({}));
  const v = body.store === "apple" ? await verifyApple(String(body.proof ?? "")) : body.store === "google" ? await verifyGoogle(String(body.proof ?? "")) : null;
  if (!v) return new Response("receipt could not be verified", { status: 402 });
  if (!["vouz.plus.monthly", "vouz.plus.annual"].includes(v.productId)) return new Response("unknown product", { status: 400 });
  const admin = createClient(url, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);
  // One store transaction can only ever belong to one account.
  const taken = await admin.from("entitlements").select("user_id").eq("original_transaction_id", v.originalTransactionId).neq("user_id", user.id).maybeSingle();
  if (taken.data) return new Response("purchase belongs to another account", { status: 409 });
  const { error } = await admin.from("entitlements").upsert({ user_id: user.id, product_id: v.productId, status: v.status, environment: v.environment,
    expires_at: new Date(v.expiresAt).toISOString(), grace_until: v.graceUntil ? new Date(v.graceUntil).toISOString() : null, will_renew: v.willRenew,
    original_transaction_id: v.originalTransactionId, verified_at: new Date().toISOString() });
  return error ? new Response("could not save", { status: 500 }) : Response.json({ status: v.status, expiresAt: v.expiresAt });
});
