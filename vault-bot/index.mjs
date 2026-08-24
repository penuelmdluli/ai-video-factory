// Genesis Vault Bot — a dedicated WhatsApp linked device that ONLY receives
// the owner's photos/videos and saves them for the content pipeline.
// (The sales agent keeps the send-capable library; this keeps the
// receive-capable one. Two linked devices, one WhatsApp number.)
import makeWASocket, {
  useMultiFileAuthState, fetchLatestBaileysVersion, downloadMediaMessage,
  DisconnectReason,
} from "@whiskeysockets/baileys";
import QRImage from "qrcode";
import pino from "pino";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const VAULT = "C:/Users/PenuelM/Documents/ai-video-factory/assets/owner_media/inbox";
const OWNER = "27792572466";
const logger = pino({ level: "silent" });
const log = (...a) => console.log(new Date().toISOString().slice(11, 19), ...a);

let backoff = 3000;
// guards the one-shot retry when a 401 arrives right after a fresh pairing
let justRetriedFreshPairing = false;

async function start() {
  const { state, saveCreds } = await useMultiFileAuthState(path.join(ROOT, "auth"));
  const { version } = await fetchLatestBaileysVersion();
  const sock = makeWASocket({ auth: state, version, logger,
    // distinct device identity — with no browser set, this device can look
    // identical to the ShopMO agent's and WhatsApp kicks one when the other
    // links (401 storm 2026-08-17)
    browser: ["Genesis Vault", "Chrome", "1.0"],
                              printQRInTerminal: false });
  sock.ev.on("creds.update", saveCreds);
  sock.ev.on("connection.update", async (u) => {
    if (u.qr) {
      await QRImage.toFile(path.join(ROOT, "qr.png"), u.qr, { width: 600, margin: 3 });
      log("QR saved to vault-bot/qr.png — scan with the bot phone (Linked Devices).");
    }
    if (u.connection === "open") log("✅ vault-bot connected. Watching for owner media.");
    if (u.connection === "close") {
      const code = u.lastDisconnect?.error?.output?.statusCode;
      log("connection closed", code || "");

      // 515 restartRequired is what WhatsApp sends IMMEDIATELY AFTER a
      // successful QR scan: the credentials are written and the socket must be
      // rebuilt at once to finish the login. It used to fall through to the
      // generic branch below and wait up to 60s, by which time the pairing had
      // lapsed; the retry then came back 401 and the self-heal deleted the
      // credentials the scan had just created. That is why every scan failed
      // (2026-08-24: 515 at 12:51:51, 401 at 12:52:55, session wiped).
      // Reconnect now, no backoff, and never treat this as a dead session.
      if (code === DisconnectReason.restartRequired) {
        log("pairing accepted — restarting socket immediately to complete login");
        setTimeout(start, 0);
        return;
      }

      if (code === DisconnectReason.loggedOut) {
        // A 401 within moments of pairing is not a stale session, it is a
        // handshake that has not settled. Wiping there destroys a good scan,
        // so retry once on the existing credentials before clearing anything.
        const credsFile = path.join(ROOT, "auth", "creds.json");
        let ageMs = Infinity;
        try { ageMs = Date.now() - fs.statSync(credsFile).mtimeMs; } catch {}
        if (ageMs < 120000 && !justRetriedFreshPairing) {
          justRetriedFreshPairing = true;
          log(`401 but credentials are ${Math.round(ageMs / 1000)}s old — ` +
              "retrying once before clearing a possibly good pairing");
          setTimeout(start, 2000);
          return;
        }
        justRetriedFreshPairing = false;
        // SELF-HEAL. This used to log "delete auth/ and re-scan" and exit,
        // pm2 restarted it, it reloaded the same dead credentials, got 401
        // again — 36,942 restarts deep, hammering WhatsApp every 5 seconds
        // and never once showing a QR. Clear the dead session ourselves and
        // come back up fresh so a QR is actually produced.
        try {
          fs.rmSync(path.join(ROOT, "auth"), { recursive: true, force: true });
          log("stale session cleared — restarting to generate a fresh QR");
        } catch (e) { log("could not clear auth:", e.message); }
        backoff = 3000;
        setTimeout(start, backoff);
      } else {
        // grow the wait so a flaky network cannot become a hot loop
        backoff = Math.min(60000, Math.max(3000, backoff * 2));
        log(`reconnecting in ${Math.round(backoff / 1000)}s`);
        setTimeout(start, backoff);
      }
    }
    if (u.connection === "open") { backoff = 3000; justRetriedFreshPairing = false; }
  });
  sock.ev.on("messages.upsert", async ({ messages, type }) => {
    if (type !== "notify") return;
    for (const m of messages) {
      try {
        const jid = m.key?.remoteJid || "";
        if (m.key?.fromMe || jid === "status@broadcast") continue;
        const senderPn = m.key?.senderPn || m.key?.participantPn || "";
        const phone = (senderPn ? String(senderPn).split("@")[0] : jid.split("@")[0]);
        if (!phone.includes(OWNER)) continue;
        const outer = m.message || {};
        const mm = outer.viewOnceMessage?.message || outer.viewOnceMessageV2?.message ||
          outer.ephemeralMessage?.message || outer.documentWithCaptionMessage?.message || outer;
        const vid = mm.videoMessage ||
          (mm.documentMessage && /video/i.test(mm.documentMessage.mimetype || "")
            ? mm.documentMessage : null);
        const img = mm.imageMessage ||
          (mm.documentMessage && /image/i.test(mm.documentMessage.mimetype || "")
            ? mm.documentMessage : null);
        if (!vid && !img) continue;
        const media = vid || img;
        // documents keep the ORIGINAL quality — WhatsApp only recompresses
        // media sent as "video"/"photo". Caption may sit on the outer wrapper.
        const caption = (media.caption ||
          outer.documentWithCaptionMessage?.message?.documentMessage?.caption ||
          "").trim();
        log(`incoming owner ${vid ? "video" : "image"}… downloading`);
        const buf = await downloadMediaMessage(m, "buffer", {},
          { logger, reuploadRequest: sock.updateMediaMessage });
        fs.mkdirSync(VAULT, { recursive: true });
        const stamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
        const fname = `${stamp}_${vid ? "video.mp4" : "image.jpg"}`;
        fs.writeFileSync(path.join(VAULT, fname), buf);
        fs.writeFileSync(path.join(VAULT, fname + ".json"), JSON.stringify({
          caption, from: phone,
          ts: Date.now(), kind: vid ? "video" : "image" }, null, 2));
        log(`saved ${fname} (${(buf.length / 1e6).toFixed(1)}MB) caption="${caption}"`);
      } catch (e) { log("save failed:", e.message); }
    }
  });
}
start();
