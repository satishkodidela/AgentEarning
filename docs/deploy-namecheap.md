# Development server on Namecheap (Stellar, cPanel)

This puts **erechnungsbote.de** online on the Namecheap products you bought:
Stellar hosting, PositiveSSL, Private Email and the domain. It takes about
60–90 minutes the first time.

Use this server for **development and testing with test data only**. It is
in a USA datacenter, and Passenger shared hosting may pause the app when
idle. Before real German customers' invoices go through it, move to an EU
server (see `docs/go-live-checklist.md`, phase D).

> **Never paste passwords, API keys or tokens into a chat, e-mail or
> GitHub.** They go only into `~/.einvoice-bridge.env` on the server.

## 1. Domain and SSL (10 min)

1. **Namecheap Dashboard > Domain List > erechnungsbote.de > Manage:**
   - **Nameservers:** keep "Namecheap Web Hosting DNS" if Namecheap set it
     when you bought hosting. DNS is then edited in cPanel > Zone Editor.
   - Otherwise use "Namecheap BasicDNS" and edit under Advanced DNS.
2. **Dashboard > SSL Certificates > PositiveSSL > Activate:**
   - Choose installation on your Namecheap hosting (cPanel).
   - Validation is automatic when the domain points to the hosting.
   - Wait until the status is "Active". It usually takes minutes, but can
     take a few hours for a brand-new domain.
3. **cPanel > Domains:** switch on **Force HTTPS Redirect** for
   `erechnungsbote.de`.

## 2. E-mail with Private Email (15 min)

1. **Dashboard > Private Email:** create three mailboxes:
   - `rechnung@erechnungsbote.de`: the app sends from it.
   - `kontakt@erechnungsbote.de`: support and the contact page.
   - `dmarc@erechnungsbote.de`: DMARC reports.
2. **DNS** (where your nameservers are managed, see step 1.1):
   - **If the domain uses Namecheap BasicDNS:** go to Advanced DNS > Mail
     Settings and choose **Private Email**. Namecheap adds the MX and SPF
     records itself.
   - **If records are edited in cPanel Zone Editor:** add them by hand:

     | Type | Name | Value |
     |---|---|---|
     | MX | `@` | `mx1.privateemail.com` (priority 10) |
     | MX | `@` | `mx2.privateemail.com` (priority 10) |
     | TXT | `@` | `v=spf1 include:spf.privateemail.com ~all` |
     | TXT | DKIM (selector as shown in Private Email settings) | copy the value Private Email shows |
     | TXT | `_dmarc` | `v=DMARC1; p=none; rua=mailto:dmarc@erechnungsbote.de` |

   - Keep only **one** SPF record. If cPanel's own mail routing is set to
     "Local", set it to **Remote** (cPanel > Email Routing). Otherwise mail
     to your own domain stays on the hosting server.
3. Note the `rechnung@` password; it goes into the server config in step 4.

## 3. Get the code onto the server (10 min)

The app needs **Python 3.11 or newer**. Check in cPanel > **Setup Python
App** that 3.11 or higher is offered. If not, ask Namecheap support, or use
the Hetzner setup instead (`deploy/setup-server.sh`).

Open **cPanel > Terminal** (or SSH, port 21098). If the repository is
private, first create a read-only GitHub token:
- GitHub > Settings > Developer settings > Fine-grained tokens.
- Only repository **AgentEarning**, permission **Contents: Read-only**.

Then:

```bash
cd ~
git clone --branch claude/determined-lovelace-gxddxl \
  https://<TOKEN>@github.com/satishkodidela/AgentEarning.git einvoice
cd einvoice && git remote set-url origin https://github.com/satishkodidela/AgentEarning.git
```

The last command removes the token from the saved remote. For updates,
run `git pull` with the token in the URL again, or run `git pull` with the
token as the password.

## 4. Create the Python app and install (15 min)

1. **cPanel > Setup Python App > Create Application:**

   | Field | Value |
   |---|---|
   | Python version | 3.11 (or the newest ≥ 3.11) |
   | Application root | `einvoice` |
   | Application URL | `erechnungsbote.de` (path empty) |
   | Application startup file | `passenger_wsgi.py` |
   | Application Entry point | `application` |
   | Passenger log file | `/home/<cpanel-user>/einvoice-data/passenger.log` |

   Click **Create**. Copy the command shown at the top, "Enter to the
   virtual environment …".
2. In the Terminal, run:

   ```bash
   source /home/<cpanel-user>/virtualenv/einvoice/3.11/bin/activate && cd ~/einvoice
   bash deploy/namecheap/install.sh
   ```

   The script:
   - installs the app;
   - creates `~/.einvoice-bridge.env` (private, mode 600) with a new
     encryption key;
   - pre-fills the Private Email SMTP host and user;
   - restarts the app;
   - runs `einvoice-bridge doctor`.
3. Edit `~/.einvoice-bridge.env` (cPanel File Manager with hidden files
   shown, or `nano ~/.einvoice-bridge.env`):
   - set `SMTP_PASSWORD=` to the `rechnung@` mailbox password;
   - **copy the `EINVOICE_SECRET_KEY` line into your password manager.**
     Without it, stored Stripe connections cannot be decrypted.
4. Check and restart:

   ```bash
   set -a; . ~/.einvoice-bridge.env; set +a
   einvoice-bridge doctor --send-test-to <your own e-mail>
   touch ~/einvoice/tmp/restart.txt
   ```

5. Open **https://erechnungsbote.de**. Upload a file in "E-Rechnung
   kostenlos prüfen" and check that the result page appears.

Updating later: `git pull`, then `bash deploy/namecheap/install.sh` inside
the virtualenv.

## 5. Connect Stripe and Paddle (test mode)

Follow `stripe-app/README.md` (Stripe test mode) and `docs/launch-setup.md`,
"Paddle billing setup" (sandbox). Put the keys into `~/.einvoice-bridge.env`
and run `touch ~/einvoice/tmp/restart.txt`. `einvoice-bridge doctor` shows
whether each part is complete.

## Troubleshooting

| Symptom | Fix |
|---|---|
| "Incomplete response" / 500 right after deploy | Read `~/einvoice-data/passenger.log`. Usually a typo in the env file. Run `einvoice-bridge doctor`. |
| Old version still showing | `touch ~/einvoice/tmp/restart.txt` |
| `pip install` fails on saxonche | Older server: run `pip install "saxonche==12.5.0"` (tested), then rerun install.sh |
| First page load slow | Passenger starts the app on demand after idle time. That's normal on shared hosting. |
| Test e-mail not arriving | Run `doctor --smtp` for the login. Check the SPF/DKIM records and Email Routing = Remote. |
