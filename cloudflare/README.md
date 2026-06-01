# Cloudflare Email Worker — `privacy@usecompli.app` → DSAR intake

When someone emails `privacy@usecompli.app`, Cloudflare hands the message to this
Worker, which POSTs the raw email body to `https://api.usecompli.app/dsar/inbox`.
Our intake parses the subject + identifiers + creates a pending DSAR request,
then fires a Slack + in-app notification.

## One-time deploy

1. Install Wrangler:
   ```bash
   npm install -g wrangler
   ```
2. Login:
   ```bash
   wrangler login
   ```
3. Deploy:
   ```bash
   cd cloudflare
   wrangler deploy
   ```
   Output should include the Worker URL — not relevant for email-triggered
   workers, but confirms the upload succeeded.

## Wire it to Email Routing

1. Cloudflare dashboard → `usecompli.app` → **Email → Email Routing**
2. If not enabled: click **Enable Email Routing**. Accept the MX records
   Cloudflare auto-adds.
3. Add a destination address (your real Gmail) and click the verification link
   Cloudflare emails you. Required at least once.
4. **Routes → Create address**:
   - Custom address: `privacy@usecompli.app`
   - Action: **Send to a Worker**
   - Worker: `email-to-dsar`
5. Save.

## Test

From any email account:
```
To: privacy@usecompli.app
Subject: GDPR Article 17 erasure request

Dear DPO,

I, Hans Müller, hereby request erasure under Article 17 GDPR.
My employee ID is E-43217.

— Hans Müller
hans.mueller@bosch.example
```

Within a few seconds:
- New DSAR row appears at `https://usecompli.app/dsar`
- Bell in the topbar pulses citrine
- If `SLACK_WEBHOOK_URL` is set, the configured Slack channel gets a Block Kit
  message with a "Review request →" button.

Click the bell or the Slack button → opens `/dsar/{id}` → approve → execute.

## Debugging

- Worker logs: `wrangler tail email-to-dsar` (real-time stream of email arrivals)
- If the email bounces with "intake refused", check the backend logs:
  `railway logs --service tracer-api`
- If the email bounces with "intake unreachable", check that `api.usecompli.app`
  resolves and that Railway is healthy.

## Why a Worker, not a forward?

A plain forward would only put the email in your inbox. We need to:
1. Parse it programmatically.
2. Create a DSAR record.
3. Fire notifications.

The Worker accomplishes all three without you owning a real mailbox.
