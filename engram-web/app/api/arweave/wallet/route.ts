/**
 * GET /api/arweave/wallet
 *
 * Returns the current Arweave wallet address and AR balance.
 *
 * AUTH REQUIRED — pass the ENGRAM_ADMIN_TOKEN as a Bearer token:
 *   Authorization: Bearer <ENGRAM_ADMIN_TOKEN>
 *
 * Fails closed: if ENGRAM_ADMIN_TOKEN is not configured in the environment,
 * all requests are rejected with 401 regardless of what is sent.
 *
 * This endpoint never generates or returns JWK private key material.
 * To generate a wallet, run locally:
 *   node -e "require('arweave').init({}).wallets.generate().then(k => console.log(JSON.stringify(k)))"
 * Then set ARWEAVE_KEY in your server environment.
 */
import { NextResponse } from "next/server";
import { getWalletBalance } from "@/lib/arweave";

export const runtime = "nodejs";

function isAuthorized(req: Request): boolean {
  const adminToken = process.env.ENGRAM_ADMIN_TOKEN;
  // Fail closed: block all access when token is not configured
  if (!adminToken) return false;
  const auth = req.headers.get("authorization") ?? "";
  return auth === `Bearer ${adminToken}`;
}

export async function GET(req: Request) {
  if (!isAuthorized(req)) {
    return NextResponse.json(
      { error: "Unauthorized. Configure ENGRAM_ADMIN_TOKEN and pass it as: Authorization: Bearer <token>" },
      { status: 401 }
    );
  }

  if (!process.env.ARWEAVE_KEY) {
    return NextResponse.json({
      status: "no_wallet",
      message:
        "No ARWEAVE_KEY configured. Generate a wallet locally and set it as an env var — " +
        "never share the key or request it over HTTP. " +
        "Generate: node -e \"require('arweave').init({}).wallets.generate().then(k => console.log(JSON.stringify(k)))\"",
    });
  }

  try {
    const { address, ar } = await getWalletBalance();
    return NextResponse.json({
      status: "ok",
      address,
      balance_ar: ar,
      env: process.env.ARWEAVE_ENV ?? "mainnet",
    });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ status: "error", error: msg }, { status: 500 });
  }
}
