# Hosting MediFlow for free (Oracle Cloud "Always Free")

MediFlow is nine services (PostgreSQL, Django, two Go services, Flask, FastAPI, Laravel and two web apps), so it
needs one real server rather than a "serverless" host. Oracle Cloud's Always Free tier gives you one for free,
permanently: an ARM server with up to 4 CPUs and 24 GB of memory. You need about 45 minutes, most of it waiting.

> This setup uses plain HTTP on the server's IP address. That's fine for a demo with made-up data. Before real
> patients' data goes in, add a domain name and HTTPS (see "Later" at the end).

## 1. Create the account (10 min)

1. Go to <https://signup.cloud.oracle.com> and sign up. Choose a **home region** close to you (for Nigeria:
   *UK South (London)* or *South Africa Central (Johannesburg)*). The home region can't be changed later.
2. Oracle asks for a card to check you're a real person. Always Free resources are never charged.

## 2. Create the server (10 min)

1. In the Oracle Cloud console: **☰ → Compute → Instances → Create instance**.
2. **Name**: `mediflow`.
3. **Image and shape → Edit**:
   - Image: **Canonical Ubuntu 22.04** (or 24.04).
   - Shape: **Change shape → Ampere → VM.Standard.A1.Flex**, **2 OCPUs** and **12 GB memory**
     (it says "Always Free-eligible").
   - If Oracle says it is "out of capacity", try again later or pick another availability domain.
4. **Networking**: keep "Create new virtual cloud network" and **Assign a public IPv4 address = Yes**.
5. **Add SSH keys → Generate a key pair for me → Save private key** (keep this file safe).
6. **Create**. When it's *Running*, copy the **Public IP address**.

## 3. Open the ports in Oracle's network (5 min)

On the instance page: **Primary VNIC → Subnet → Security → Default security list → Add ingress rules**:

| Source CIDR | IP protocol | Destination port range |
|---|---|---|
| `0.0.0.0/0` | TCP | `8080-8082` |

(The install script opens the same ports in the server's own firewall.)

## 4. Install MediFlow (20 min, mostly waiting)

From your computer (Git Bash on Windows), with the key file you saved:

```bash
chmod 600 ~/Downloads/ssh-key-*.key
ssh -i ~/Downloads/ssh-key-*.key ubuntu@YOUR_SERVER_IP
```

Then, on the server:

```bash
curl -fsSL https://raw.githubusercontent.com/MediFlow-io/mediflow-platform/main/deploy/install.sh | bash
```

When it finishes, it prints the three addresses and the sign-in passwords:

```
Staff app          http://YOUR_SERVER_IP:8080
Student dashboard  http://YOUR_SERVER_IP:8081
Admin console      http://YOUR_SERVER_IP:8082
```

The passwords are also saved on the server in `~/mediflow-platform/deploy/.credentials`.

## Everyday tasks

| To | Run on the server |
|---|---|
| Update to the latest `main` | the same `curl … install.sh \| bash` command (secrets and data are kept) |
| See logs | `cd ~/mediflow-platform && docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml --env-file deploy/.env logs -f --tail=100` |
| Stop / start | same command with `down` / `up -d` (data is kept in Docker volumes) |
| Back up the database | `docker compose … exec -T db pg_dump -U mediflow mediflow > backup.sql` |

## What the install does

- Installs Docker, downloads the code to `~/mediflow-platform`.
- Writes `deploy/.env` once with fresh secrets: database password, Django secret key, JWT signing keys,
  the internal AI token and the admin console key. It is never committed; later runs reuse it.
- Starts everything with production settings (`deploy/docker-compose.prod.yml`): Django debug off, only the
  three web ports published, every service restarts automatically after a reboot.
- Creates the demo departments and the `admin`, `manager`, `doctor` and `nurse` accounts, and replaces their
  well-known demo passwords with random ones.

CI runs this same script on every pull request ("Production install" job), so `main` stays installable.

## If something goes wrong

| Symptom | Fix |
|---|---|
| The browser can't connect at all | Check step 3 (Oracle security list). Then on the server: `curl -I localhost:8080` |
| Install stops with "Some services aren't answering" | Run the logs command above and look for the first error |
| "Out of capacity" when creating the server | Try another availability domain, or 1 OCPU / 6 GB, or try again later |
| Lost the passwords | `cat ~/mediflow-platform/deploy/.credentials` on the server |

## Later: a domain and HTTPS (before real patient data)

1. Point a domain (or three subdomains) at the server's IP.
2. Put Caddy in front: it gets HTTPS certificates automatically. Set `PUBLIC_SCHEME=https` and
   `PUBLIC_HOST=your.domain` in `deploy/.env`, then run the install again.
3. Turn on two-step sign-in for clinical staff: `MFA_REQUIRED_ROLES=admin,doctor,nurse` in `deploy/.env`.
