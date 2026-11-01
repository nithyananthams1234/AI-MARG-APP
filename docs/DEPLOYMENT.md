# MARG – Production deployment

> **Status:** the deployment configuration is prepared but **not yet executed**.
> No paid resource has been created and nothing has been deployed publicly.
> Docker was not available on the development machine, so the images and
> `docker compose` stack below have **not been built or run yet**. Do a full
> dry run on the server (step 6) before you share the URL.

## 1. Target architecture (one VM, Docker Compose)

```
Internet ──HTTPS──► Caddy "edge" (ports 80/443, Let's Encrypt)
                     ├── /            → MARG web app (static Expo export)
                     ├── /api/*       → backend (FastAPI)        ─┐
                     └── /api/v1/integrations/* → 404 (internal) │ internal network only
                                                                  │
 backend ──► postgres (marg_db)                                   │
 backend ──► classroom-coach ──► NVIDIA API Catalog + ChromaDB volume
 backend ◄─► mentor-intelligence ──► NVIDIA API Catalog
 worker  ──► postgres (AI jobs, reminders)
 mentor-intelligence ──► postgres (marg_mentor_intelligence, schema mie)
 backend ──► S3-compatible bucket (evidence files)
 backup.sh (cron) ──► S3-compatible bucket (nightly pg_dump of both DBs)
```

Why this shape:

- **Classroom Coach** uses NVIDIA-hosted inference, sentence-transformers (about 1–2 GB)
  and the knowledge-base vector store. The LLM itself no longer runs on the VM.
- **One VM** keeps the hackathon demo cheap and simple. Everything except the edge
  proxy stays private. PostgreSQL is never exposed.
- **Evidence files and backups go to object storage**, not the VM disk.

## 2. What you need (and what costs money)

| Item | Recommendation | Approx. cost (verify before buying) |
|---|---|---|
| VM: 4–8 vCPU, **16 GB RAM**, 80+ GB SSD, Ubuntu 24.04 | Options below | about $40–150 / month, depending on provider and region |
| Object storage (evidence + backups) | Cloudflare R2 | Free tier: 10 GB-month storage, zero egress, then $0.015 per GB-month |
| Domain name | Any registrar, or a subdomain you already own | about $10–15 / year (optional; see note) |
| NVIDIA API Catalog (both AI services) | NVIDIA API key | Usage and trial limits depend on the selected NVIDIA model/account |
| TLS certificates | Let's Encrypt via Caddy | Free |

VM price references, checked October 2026. Prices changed a lot in 2026, so
confirm on the provider site:

- DigitalOcean Basic Droplet, 8 vCPU / 16 GB: about $96 / month. Weekly backups add 20%.
- Hetzner Cloud CPX41, 8 vCPU / 16 GB: prices rose sharply in June 2026 and some
  plans have limited availability. Check hetzner.com for the current EU price.
- The embedding model and vector store remain local to the Coach service; a GPU is not required.

Without a domain: the VM's public IP plus a free wildcard DNS name such as
`<ip>.sslip.io` works with Let's Encrypt. That is fine for a demo; for real users,
use a proper domain.

**Approval needed:** creating the VM, the R2 account/buckets and buying a domain
are paid or outward-facing actions. None of them has been done.

## 3. Prepare secrets

On your machine, generate random secrets, one per variable:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

Copy `deploy/.env.example` to `deploy/.env` **on the server only** (`chmod 600`)
and fill in every value. Rules:

- `COACH_API_KEY`, `MIE_ENGINE_API_KEY` and `MIE_SERVICE_KEY` must all be different random values.
- `NVIDIA_API_KEY` is a server-side provider credential shared by the two AI services. Never place it in frontend configuration.
- `COACH_NVIDIA_MODEL` and `MIE_NVIDIA_MODEL` must be model IDs available to your NVIDIA API account.
- `JWT_SECRET_KEY` must be at least 32 characters. The backend refuses to start in production otherwise.
- Never commit `.env`. The repository `.gitignore` files exclude it.

## 4. Provision the server (once)

```bash
# Ubuntu 24.04, as a sudo user
sudo apt update && sudo apt -y upgrade
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER && newgrp docker
sudo apt -y install awscli ufw
sudo ufw allow OpenSSH && sudo ufw allow 80,443/tcp && sudo ufw enable   # only 22/80/443 open
```

DNS: create an `A` record `MARG_DOMAIN → <server IP>`.

## 5. Upload code and the knowledge base

```bash
sudo mkdir -p /opt/marg && sudo chown $USER /opt/marg
git clone <your private repo> /opt/marg          # contains backend/, frontend/, deploy/ ...
# Knowledge base: not in git (about 1 GB; copyrighted source PDFs). Copy from your PC:
rsync -av Marg-LLM/data/chroma_db/ server:/opt/marg/deploy/data/classroom-coach/chroma_db/
rsync -av Marg-LLM/data/pdfs/rename_mapping.csv server:/opt/marg/deploy/data/classroom-coach/
```

The vector store only needs `chroma_db/` and `rename_mapping.csv`. The PDFs themselves
are not needed at runtime. Repository folder names: the compose file expects
`../Marg-AppBackend`, `../Marg-LLM`, `../MARG-Mentor-Intelligence` and
`../Marg-AppFrontend` next to `deploy/`. Adjust the `build:` paths if the
repository uses other names.

## 6. First start

```bash
cd /opt/marg/deploy
docker compose --env-file .env build
docker compose --env-file .env up -d postgres
docker compose --env-file .env run --rm backend alembic upgrade head   # backend schema
docker compose --env-file .env run --rm mentor-intelligence alembic upgrade head
docker compose --env-file .env up -d
docker compose ps
```

Create real accounts. The demo seed must **not** be used for real users:

```bash
docker compose run --rm backend python -m app.database.seed_roles
docker compose run --rm backend python -m app.database.create_mentor    # interactive
```

School assignments are made by an Administrator through `POST /api/v1/mentor-schools/`.

### Hosted demo for the evaluation (optional)

To run the hackathon demo with fictional data, use a **separate** database named
`marg_demo` (the seed refuses any other name):

```bash
docker compose exec postgres psql -U postgres -c "CREATE DATABASE marg_demo OWNER marg_app;"
# point DATABASE_URL at marg_demo for the demo deployment, run migrations, then:
docker compose run --rm -e DEMO_PASSWORD='<strong password>' -e ALLOW_DEMO_SEED_IN_PRODUCTION=1 backend python -m app.database.seed_demo
```

## 7. Verify (smoke test)

```bash
curl -fsS https://$MARG_DOMAIN/health                 # {"status":"ok"}
curl -fsS https://$MARG_DOMAIN/health/ready           # database + migrations ok
curl -s -o /dev/null -w "%{http_code}\n" https://$MARG_DOMAIN/api/v1/integrations/mentor-intelligence/mentors   # must be 404
docker compose exec backend python -c "import urllib.request;print(urllib.request.urlopen('http://classroom-coach:8001/health/ready').read())"
docker compose exec backend python -c "import urllib.request;print(urllib.request.urlopen('http://mentor-intelligence:8002/health/ready').read())"
```

Then sign in through the browser and run the scenarios in `docs/DEMO_GUIDE.md`.

## 8. Logging and monitoring

- All services log to stdout: `docker compose logs -f backend` and so on. The backend
  and Coach log one line per request with a request ID (`X-Request-ID`), and
  Mentor Intelligence logs JSON (`LOG_FORMAT=json`).
- Health endpoints: `/health` and `/health/ready` (backend), `/health/ready`
  (Coach checks NVIDIA model access and vector store), `/health/ready` (Mentor Intelligence).
- External uptime check (free tiers exist, e.g. UptimeRobot) on
  `https://$MARG_DOMAIN/health/ready`.
- AI usage and cost: Mentor Intelligence records every NVIDIA call in `mie.llm_usage`
  and enforces daily token budgets. For cost figures, set `LLM_PRICING`.

## 9. Backups and recovery

- **Database:** `deploy/backup.sh` dumps both databases (`pg_dump -Fc`), checks each
  archive, and uploads it to `S3_BACKUP_BUCKET`. Schedule it with cron
  (02:15 UTC daily) and set a bucket lifecycle rule (for example, 30-day retention).
- **Evidence files:** already in object storage. Enable bucket versioning for
  protection against deletion.
- **Knowledge base:** keep the original `chroma_db/` and PDFs on your PC or in a
  private bucket. A local copy was made at `D:\AI-MARG-backups\chroma_db_2026-10-31`.
- **Restore:** `./restore.sh marg_db <file.dump>`. It asks for confirmation,
  stops the writers, then runs `pg_restore --clean`. Test a restore once before
  the evaluation.

## 10. Updating and rollback

```bash
cd /opt/marg && git fetch && git checkout <release-tag>
cd deploy && ./backup.sh                      # always back up before migrating
docker compose build && docker compose run --rm backend alembic upgrade head
docker compose up -d
```

**Rollback:**

1. `git checkout <previous-tag> && docker compose build && docker compose up -d`.
2. All migrations added during the integration are additive, so older code keeps
   working with the newer schema. Only run `alembic downgrade` if a migration itself
   is faulty, and only after a backup.
3. If data is damaged, restore the last backup with `restore.sh`.

## 11. Mobile app (Android) – optional

The web app runs on phones through the browser at `https://$MARG_DOMAIN`. For a
native Android build, use EAS (`npx eas-cli@latest build -p android --profile preview`)
with `EXPO_PUBLIC_API_URL=https://$MARG_DOMAIN/api/v1`. EAS needs an Expo account,
and its free tier has limited build minutes.

## Sources for prices (checked October 2026)

- [DigitalOcean pricing overview (third-party)](https://onedollarvps.com/pricing/digitalocean-pricing)
- [Hetzner price adjustment 2026](https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/)
- [Hetzner 2026 increases analysis](https://webhosting.today/2026/06/18/hetzners-price-increases-reached-209-the-30-headline-applied-to-a-different-tier/)
- [Cloudflare R2 pricing](https://developers.cloudflare.com/r2/pricing/)
