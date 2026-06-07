# Running an Engram Miner on Windows

This guide gets you mining on **Bittensor subnet 450 (testnet)** from a Windows
PC. The recommended path uses **Docker Desktop**, so you don't have to install
Python, Rust, or PyTorch on Windows — everything runs inside a container.

> **Why Docker?** Bittensor and the ML stack (PyTorch, sentence-transformers,
> faiss) are painful to build natively on Windows. Docker gives every Windows
> machine the same Linux runtime the validator expects, so your miner scores
> correctly out of the box.

---

## What you need

- **Windows 10/11** (64-bit) with virtualization enabled in BIOS.
- **[Docker Desktop](https://www.docker.com/products/docker-desktop/)** with the
  WSL 2 backend (the default). Install it, launch it once, and wait for the
  whale icon to go steady.
- **~6 GB free disk** for the image and model.
- A little **testnet TAO** to register (free from the faucet — see below).

---

## Quick start (one script)

1. Open **PowerShell** and clone the repo:

   ```powershell
   git clone https://github.com/Dipraise1/-Engram-.git engram
   cd engram
   ```

2. Run the setup script:

   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\setup_miner.ps1
   ```

   It will:
   - check Docker Desktop is running,
   - generate `.env.miner`,
   - build the miner image,
   - create your wallet (if you don't have one),
   - walk you through registration,
   - start the miner.

That's it. Skip to [Watching your miner](#watching-your-miner).

If you'd rather do it by hand, follow the manual steps below.

---

## Manual steps

### 1. Configure

```powershell
Copy-Item .env.miner.example .env.miner
notepad .env.miner
```

Make sure these match the validator (they're the defaults — **don't change the
embedder**):

```ini
WALLET_NAME=engram
WALLET_HOTKEY=miner
SUBTENSOR_NETWORK=test
NETUID=450

EXTERNAL_IP=<your public IP>       # validators must reach you here
MINER_PORT=8091

USE_LOCAL_EMBEDDER=true
LOCAL_EMBEDDING_MODEL=all-MiniLM-L6-v2
EMBEDDING_DIM=384
VECTOR_STORE_BACKEND=faiss
```

> **EXTERNAL_IP** must be your *public* IP and port 8091 must be reachable from
> the internet, or validators can't query you and you'll score 0. Find it at
> <https://ifconfig.me>. See [Networking](#networking--port-forwarding).

### 2. Point Docker at your wallet folder

Wallet keys live on **your** machine and are mounted into the container, so they
survive rebuilds and you stay in control of them:

```powershell
$env:ENGRAM_WALLET_DIR = "$env:USERPROFILE\.bittensor"
```

### 3. Build the image

```powershell
docker compose -f docker-compose.windows.yml build miner
```

First build downloads PyTorch and the embedding model — a few minutes. Later
builds are cached.

### 4. Create a wallet

If you don't already have one (this saves keys to `%USERPROFILE%\.bittensor`):

```powershell
docker compose -f docker-compose.windows.yml run --rm -it miner `
  btcli wallet new_coldkey --wallet.name engram

docker compose -f docker-compose.windows.yml run --rm -it miner `
  btcli wallet new_hotkey --wallet.name engram --wallet.hotkey miner
```

> **Write down the mnemonic.** It's the only way to recover your wallet. Back up
> the whole `%USERPROFILE%\.bittensor` folder somewhere safe.

### 5. Get testnet TAO and register

```powershell
# Free testnet TAO
docker compose -f docker-compose.windows.yml run --rm -it miner `
  btcli wallet faucet --wallet.name engram --subtensor.network test

# Register your hotkey on subnet 450
docker compose -f docker-compose.windows.yml run --rm -it miner `
  btcli subnet register --netuid 450 --wallet.name engram --wallet.hotkey miner --subtensor.network test
```

### 6. Start the miner

```powershell
docker compose -f docker-compose.windows.yml up -d miner
```

---

## Watching your miner

```powershell
# Follow logs
docker compose -f docker-compose.windows.yml logs -f miner

# Liveness check (should return JSON)
curl http://localhost:8091/health

# Stop / restart
docker compose -f docker-compose.windows.yml down
docker compose -f docker-compose.windows.yml up -d miner
```

A healthy miner logs `Miner HTTP server live on 0.0.0.0:8091` and, once
registered, `Axon registered on-chain`. Validators score every ~120s; you'll see
incoming `IngestSynapse` / `ChallengeSynapse` requests in the logs.

---

## Networking / port forwarding

Validators connect *inbound* to your `EXTERNAL_IP:8091`. On a home connection
you usually must:

1. **Forward port 8091/TCP** on your router to your PC's local IP.
2. **Allow it through Windows Firewall:**

   ```powershell
   New-NetFirewallRule -DisplayName "Engram Miner 8091" `
     -Direction Inbound -Protocol TCP -LocalPort 8091 -Action Allow
   ```

3. Confirm `EXTERNAL_IP` in `.env.miner` is your public IP (not `192.168.x.x`).

Test reachability from another network (e.g. your phone on mobile data):
`http://<your-public-ip>:8091/health`.

If you can't forward ports (corporate network, CGNAT), use a VPS or the
[cloud / phone mining option](cloud-mining.md) instead.

---

## Alternative: WSL 2 (no Docker)

Prefer a native Linux setup? Install **WSL 2** and run the standard Linux
installer inside an Ubuntu shell:

```powershell
wsl --install -d Ubuntu     # then reboot, open "Ubuntu" from the Start menu
```

Inside Ubuntu:

```bash
sudo bash -c "$(curl -fsSL https://raw.githubusercontent.com/Dipraise1/-Engram-/main/scripts/setup_miner.sh)"
```

This is the same script Linux/VPS operators use (systemd service, Qdrant,
optional Rust build). See [miner.md](miner.md) for details. Note: port 8091 must
still be forwarded to your Windows host and on to WSL.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Cannot connect to the Docker daemon` | Docker Desktop isn't running. Launch it and wait for the whale icon. |
| Build fails on `pip install` | Out of disk or a flaky download. Free space, then `docker compose -f docker-compose.windows.yml build --no-cache miner`. |
| `Hotkey not registered` in logs | Run the faucet + register steps (step 5). |
| Scoring 0 / validators never call | Port 8091 isn't reachable. Check router forwarding, Windows Firewall, and that `EXTERNAL_IP` is your public IP. |
| Wallet "not found" | `ENGRAM_WALLET_DIR` must point at the folder containing `wallets\`. Default is `%USERPROFILE%\.bittensor`. |
| Want to wipe and restart | `docker compose -f docker-compose.windows.yml down -v` (this deletes the FAISS index, **not** your wallet). |

---

## How it fits together

```
Windows PC
 ├─ Docker Desktop (WSL2 backend)
 │   └─ engram-miner container
 │        ├─ aiohttp HTTP API on :8091  ──>  validators query / challenge
 │        ├─ all-MiniLM-L6-v2 embedder (384-dim, matches validator)
 │        └─ FAISS vector index  ──>  docker volume (persists)
 └─ %USERPROFILE%\.bittensor  ──mounted──>  /root/.bittensor (your keys)
```

Full configuration reference: [miner.md](miner.md).
