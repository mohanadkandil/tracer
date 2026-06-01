// email-to-dsar — Cloudflare Email Worker
//
// Triggered when an email arrives at privacy@usecompli.app.
// Reads the raw RFC 5322 message + POSTs to our intake endpoint, which parses
// the subject name, identifiers, and creates a pending DSAR request.

export default {
  /**
   * @param {ForwardableEmailMessage} message
   * @param {Env} env
   */
  async email(message, env) {
    const apiBase = env.FORGETTER_API_BASE || "https://api.usecompli.app";

    // Pull the raw email body out of the stream
    const reader = message.raw.getReader();
    const chunks = [];
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      chunks.push(value);
    }
    const decoder = new TextDecoder("utf-8");
    const rawBody = chunks.map((c) => decoder.decode(c, { stream: true })).join("");

    let res;
    try {
      res = await fetch(`${apiBase}/dsar/inbox`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Source": "cloudflare-email-worker",
        },
        body: JSON.stringify({
          body: rawBody,
          source: "email",
          requester_email: message.from,
        }),
      });
    } catch (err) {
      // Network failure — bounce so sender knows
      message.setReject(`intake unreachable: ${String(err).slice(0, 200)}`);
      return;
    }

    if (!res.ok) {
      const detail = await res.text().catch(() => res.statusText);
      message.setReject(`intake refused (${res.status}): ${detail.slice(0, 200)}`);
      return;
    }
    // Accept the email — backend already wrote the DSAR row + fired notifications
  },
};
