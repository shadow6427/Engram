# Cloud Mining — Mine Engram from Your Phone

Mine on Bittensor subnet 450 from any device. Your phone holds the identity and pays for compute; a managed node on **Akash Network** does the heavy lifting.

---

## How It Works

```
Your Phone                      Cloud Gateway              Akash Node
──────────                      ─────────────              ──────────
Generate sr25519 keypair
  (stays on device)

POST /sessions ────────────►   Verify x402 payment
  X-Payment: <USDC receipt>     │
  hotkey: <your pubkey>         │  Dexter facilitator
  tier: standard                │  confirms on-chain tx
  duration_hours: 24            │
                                Deploy miner container
                                to Akash Network ──────►  Docker: miner.py
                                                           Qdrant vector store
                                Wait for provider ◄─────  /health OK
◄──── {                    ◄───
  session_id,
  node_endpoint,
  expires_at
}

Poll /sessions/{id} every 30s:
  vectors, proof_rate, block ◄── gateway fetches from
                                  node /stats
```

**Privacy guarantee:** Your sr25519 private key never leaves your phone. It signs gateway auth headers (not Bittensor extrinsics). All on-chain Bittensor operations are handled by the managed node using its own pre-registered hotkey.

---

## Mobile App

The Engram mobile app is a React Native (Expo) app with three screens:

| Screen | Function |
|--------|----------|
| **Wallet** | Generate / manage your sr25519 keypair. View Bittensor subnet 450 stats via raw JSON-RPC (no SDK). |
| **Start Mining** | Pick compute tier and duration, pay with USDC on Base via Dexter (x402), launch node. |
| **Dashboard** | Live stats from your active node — vectors stored, proof rate, latency, block. Stop session. |

### Building the app

```bash
cd mobile
cp .env.example .env
# Set EXPO_PUBLIC_GATEWAY_URL to your gateway endpoint

npm install
npx expo start          # dev server
npx expo run:android    # Android
npx expo run:ios        # iOS
eas build --platform android  # production APK
```

### Key design choices

- **sr25519 via WebAssembly** (`@polkadot/wasm-crypto`) — no native crypto compilation on Android
- **Bittensor reads** use raw Substrate JSON-RPC HTTP calls — no `bittensor` SDK on the phone
- **Bittensor writes** (register axon, set weights) are handled entirely by the cloud node
- **x402 payment** is a pure HTTPS call — no Web3 library needed

---

## Compute Tiers

| Tier | vCPU | RAM | Storage | Approx price |
|------|------|-----|---------|--------------|
| **Lite** | 1 | 2 GB | 10 GB | ~$0.10/hr |
| **Standard** | 2 | 4 GB | 20 GB | ~$0.20/hr |
| **Pro** | 4 | 8 GB | 40 GB | ~$0.36/hr |

Prices are approximate — Akash providers bid competitively, so actual cost may be lower. Payment is in USDC on Base (or other x402-supported networks).

---

## Payment — x402 via Dexter Cash

Engram uses the **x402 open standard** for payment. When you hit "Pay & Start Mining":

1. App requests session creation from the gateway
2. Gateway returns `HTTP 402` with payment requirements (amount, network, recipient)
3. App builds and signs an on-chain USDC transfer via Dexter Cash
4. App resends request with `X-Payment: <receipt>` header
5. Gateway verifies receipt with Dexter facilitator
6. Node is provisioned

No account required. No KYC. Payment settles in seconds on Base.

---

## Running the Cloud Gateway

The gateway is a standalone aiohttp server (`neurons/cloud_gateway.py`) that the mobile app talks to directly.

### Environment variables

| Variable | Required | Description |
|---|---|---|
| `X402_RECIPIENT_ADDRESS` | Yes | Your USDC wallet address on Base (receives payments) |
| `X402_FACILITATOR_URL` | Yes | Dexter facilitator endpoint (https://x402.dexter.cash) |
| `X402_NETWORK` | No | Payment network (default: `base`) |
| `CLOUD_PRICE_PER_HOUR_USD` | No | Hourly rate (default: `0.10`) |
| `AKASH_OWNER_ADDRESS` | Yes | Akash wallet address that pays for compute |
| `AKASH_NODE_URL` | No | Akash REST API (default: https://api.akash.network) |
| `AKASH_CHAIN_ID` | No | default: `akashnet-2` |
| `GATEWAY_PORT` | No | HTTP port (default: `9000`) |
| `GATEWAY_AUTH_REQUIRED` | No | Set to `0` for dev mode (skips sig verification) |

### Start the gateway

```bash
# Install dependencies
pip install -e .

# Configure
export X402_RECIPIENT_ADDRESS=0xYourUSDCWalletOnBase
export X402_FACILITATOR_URL=https://x402.dexter.cash
export AKASH_OWNER_ADDRESS=akash1yourwalletaddress

# Run
python neurons/cloud_gateway.py --port 9000
```

### Point the mobile app at it

```bash
# mobile/.env
EXPO_PUBLIC_GATEWAY_URL=https://your-gateway-domain.com
```

---

## Running Miners on Akash (operator setup)

The gateway auto-deploys miner containers to Akash when a session is created. To use this:

### 1. Set up an Akash wallet

```bash
# Install Akash CLI
curl https://raw.githubusercontent.com/akash-network/node/main/install.sh | bash

# Create wallet and fund with AKT
akash keys add engram-operator
akash query bank balances $(akash keys show engram-operator -a)
```

### 2. Configure the SDL manifest

The SDL for each session is auto-generated by `engram/cloud/akash_sdl.py`. The miner Docker image is pulled from GHCR:

```
ghcr.io/dipraise1/engram:latest
```

Override with `ENGRAM_MINER_IMAGE` env var to use a custom image.

### 3. Fund the operator wallet

Akash deployments require AKT for gas + provider escrow. Recommended: keep at least 10 AKT in the operator wallet. Providers are paid from the deployment escrow automatically.

---

## Security Model

| Threat | Defence |
|--------|---------|
| Phone private key exposure | Key stored in device secure enclave (Expo SecureStore) — never sent |
| Gateway impersonation | Every gateway request signed by phone's sr25519 hotkey |
| Session hijacking | Session gated by hotkey — only the controller hotkey can read or stop it |
| Payment fraud | x402 receipt verified on-chain via Dexter facilitator before provisioning |
| Private memory cross-access | Namespace isolation enforced at every miner endpoint (retrieve, list, delete) |
| Memory tampering | Merkle commitment over full corpus — `GET /commitment` proves integrity |

---

## API Reference

### Gateway endpoints

```
GET  /health                       — liveness check
GET  /tiers                        — compute tiers and pricing
GET  /nodes                        — pool availability
GET  /bittensor/metagraph?netuid=N — raw subnet state (no auth, pure JSON-RPC)

POST   /sessions                   — create session (x402 payment required)
GET    /sessions/{id}              — session status + live stats
DELETE /sessions/{id}              — stop session early
GET    /sessions/hotkey/{hk}       — all sessions for a hotkey
```

### Create session

**Request:**
```http
POST /sessions
X-Hotkey: 5GrwvaEF...
X-Timestamp: 1716000000000
X-Sig: <sr25519 sig of "engram-cloud:POST:/sessions:{timestamp}">
X-Payment: <base64-encoded x402 receipt>
Content-Type: application/json

{
  "tier": "standard",
  "duration_hours": 24
}
```

**Response (202 Accepted):**
```json
{
  "session_id": "a1b2c3d4-...",
  "status": "provisioning",
  "expires_at": 1716086400.0,
  "remaining_seconds": 86400,
  "amount_paid_usd": 2.4
}
```

### Get session

```http
GET /sessions/a1b2c3d4-...
X-Hotkey: 5GrwvaEF...
X-Timestamp: 1716000000000
X-Sig: <sig>
```

```json
{
  "session_id": "a1b2c3d4-...",
  "status": "active",
  "node_endpoint": "https://provider.akash.host:32001",
  "remaining_seconds": 82341,
  "stats": {
    "vectors": 1842,
    "proof_rate": 0.9983,
    "p50_latency_ms": 43.2,
    "queries_today": 287,
    "block": 3841920
  }
}
```
