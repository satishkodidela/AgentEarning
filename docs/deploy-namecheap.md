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

## 1. Domain and SSL (10–40 min, mostly waiting)

Do this **before** creating the Python app (step 4).

1. **Point the domain at the hosting.** Keep the nameservers on
   **Namecheap BasicDNS**. Switching a `.de` domain to "Namecheap Web
   Hosting DNS" often fails with "Oops, something went wrong": the `.de`
   registry first checks that the new nameservers already hold the
   domain's settings. Instead, go to Domain List > erechnungsbote.de >
   Manage > **Advanced DNS**:
   - Find the hosting IP in cPanel's sidebar under "Shared IP Address".
   - Delete the default parking records (CNAME `www` → parkingpage, URL
     Redirect `@`).
   - Add the A record and save each row with ✓:

     | Type | Host | Value |
     |---|---|---|
     | A Record | `@` | hosting IP |
     | CNAME Record | `www` | `erechnungsbote.de.` |

   - Under **Mail Settings**, choose **Private Email**. This adds the MX
     and SPF records.

   With BasicDNS, all later records (DKIM, DMARC) go in this Advanced DNS
   tab too, not in cPanel's Zone Editor.
2. Wait until `http://erechnungsbote.de` shows the default hosting page.
   This usually takes 5–30 minutes.
3. **SSL, with DNS validation so that `www` is included.** File-upload
   (HTTP) validation only covers `erechnungsbote.de`. Browsers then warn on
   `www.erechnungsbote.de`, and cPanel's Force HTTPS switch stays grey.
   Namecheap's "server-side automation" (SSL Manager) also issues the bare
   domain only. Use the manual route:
   1. cPanel > SSL/TLS > **Requests** > generate a new request with a new
      2048-bit RSA key. Enter `erechnungsbote.de` and
      `www.erechnungsbote.de`, one per line. Copy the
      `-----BEGIN CERTIFICATE REQUEST-----` block. It is not secret. The
      private key stays on the server.
   2. Namecheap > SSL Certificates > Activate (or **Reissue**) > **Manage
      SSL manually**. Paste the request and choose **DNS (CNAME)**
      validation.
   3. In Advanced DNS, add the CNAME record it shows. In **Host**, enter only
      the part before `.erechnungsbote.de`. The value is `dcv.ssl.com`.
      Wait 10–60 minutes, then click **Verify**.
   4. When the status is ACTIVE, download the zip with the `.crt` and
      `.ca-bundle` files. There is no key in it, and that is correct.
   5. cPanel > SSL/TLS > **Installation**: paste the `.crt` and click
      **Autofill by Certificate**, not "by Domain". This fills the private
      key from the server. Check that the Domains line shows both names,
      then click **Install**.
4. When SSL/TLS Status shows both names green, go to cPanel > Domains and
   switch on **Force HTTPS Redirect** for `erechnungsbote.de`. The switch can
   stay locked with "Some aliases for this domain may not have a working SSL
   certificate". That refers to `mail.`, `cpanel.` and similar names. If so,
   leave it off: `install.sh` sets `EINVOICE_FORCE_HTTPS=1`, and the app then
   redirects `http://` page views to `https://` itself.

Certificates now last about 200 days (the CA/B Forum limit since March
2026). Set a reminder to reissue about two weeks before the expiry date.
The reissue is free within the subscription. The DNS route works the same
way after the Python app has taken over the domain. HTTP validation files
are still served from `~/public_html/.well-known`
(`EINVOICE_WELL_KNOWN_DIR`).

## 2. E-mail with Private Email (15 min)

1. **Dashboard > Private Email:** create three mailboxes:
   - `rechnung@erechnungsbote.de`: the app sends from it.
   - `kontakt@erechnungsbote.de`: support and the contact page.
   - `dmarc@erechnungsbote.de`: DMARC reports.
2. **DNS** (where your nameservers are managed, see step 1.1):
   - **If the domain uses Namecheap BasicDNS:** go to Advanced DNS > Mail
     Settings and choose **Private Email**. Namecheap adds the MX and SPF
     records itself. Add the `_dmarc` TXT record from the table below
     under Host Records.
   - **If records are edited in cPanel Zone Editor:** add them by hand:

     | Type | Name | Value |
     |---|---|---|
     | MX | `@` | `mx1.privateemail.com` (priority 10) |
     | MX | `@` | `mx2.privateemail.com` (priority 10) |
     | TXT | `@` | `v=spf1 include:spf.privateemail.com ~all` |
     | TXT | DKIM host as shown in Private Email settings | copy the value Private Email shows |
     | TXT | `_dmarc` | `v=DMARC1; p=none; rua=mailto:dmarc@erechnungsbote.de` |

   - **DKIM, both cases:** BasicDNS is supposed to add it automatically,
     but it may be missing. Then Gmail's "Show original" says
     `DKIM: 'FAIL'`. Go to Dashboard > Private Email > Manage > **Show
     DKIM**, and add a TXT record with the host it shows and the whole
     value on one line. The host is `privateemail._domainkey` for
     subscriptions since June 2026, `default._domainkey` before that.
   - Keep only **one** SPF record. If cPanel's own mail routing is set to
     "Local", set it to **Remote** (cPanel > Email Routing). Otherwise mail
     to your own domain stays on the hosting server.
3. Note the `rechnung@` password; it goes into the server config in step 4.
4. **Test:** log in at privateemail.com as `rechnung@`, send a mail to a
   Gmail address, and open it with ⋮ > **Show original**. SPF, DKIM and DMARC
   must all say PASS.

## 3. Get the code onto the server (10 min)

The app needs **Python 3.11 or newer**. Check in cPanel > **Setup Python
App** that 3.11 or higher is offered. If not, ask Namecheap support, or use
the Hetzner setup instead (`deploy/setup-server.sh`).

Open **cPanel > Terminal** (or SSH, port 21098). The repository is public,
so no token is needed:

```bash
cd ~
git clone --branch claude/determined-lovelace-gxddxl \
  https://github.com/satishkodidela/AgentEarning.git einvoice
```

If you make the repository private later, create a read-only GitHub token:
- GitHub > Settings > Developer settings > Fine-grained tokens.
- Only repository **AgentEarning**, permission **Contents: Read-only**.

Then enter the token as the password when `git pull` asks for one.

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
   einvoice-bridge doctor --send-test-to <your own e-mail>
   touch ~/einvoice/tmp/restart.txt
   ```

   `doctor` reads `~/.einvoice-bridge.env` automatically. Run it inside the
   app's virtualenv.

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
| Site hangs, then 503; `stderr.log` says "Reached max children process limit" | Requests are stuck in the app. Update (`git pull`, rerun install.sh); the entry point now starts its worker thread after LiteSpeed forks. If processes are still stuck, run `pkill -u $USER -f lswsgi` and `touch ~/einvoice/tmp/restart.txt`. |
| `pip install` fails on saxonche | Older server: run `pip install "saxonche==12.5.0"` (tested), then rerun install.sh |
| First page load slow | Passenger starts the app on demand after idle time. That's normal on shared hosting. |
| Test e-mail not arriving | Run `doctor --smtp` for the login. Check the SPF/DKIM records and Email Routing = Remote. |
