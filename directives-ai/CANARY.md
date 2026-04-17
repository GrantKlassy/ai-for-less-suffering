# Prompt: Add a PGP-Signed Warrant Canary to My Website

Paste the prompt below into Claude Code (or any capable coding agent) at the root of your website repo. Fill in the bracketed values first.

---

## THE PROMPT

I want to add a **PGP-signed warrant canary** to my website, modeled on the EFF/Apple-style transparency statement but fully self-hosted, independently verifiable, and renewed on every deploy.

Fill in these values before you start:

- **Organization name (legal):** `[COMPANY LLC]`
- **Primary domain:** `[example.com]`
- **Canary signing email:** `[canary@example.com]`
- **Canary validity window:** `90 days` (quarterly --- change if you want)
- **Web framework:** `[Astro / Next.js / Hugo / plain HTML / etc.]`
- **Public asset directory:** `[public/ or static/ or whatever your framework uses]`
- **Page route for the canary:** `/canary` (or `/transparency` --- your call)

### What a warrant canary is (context for you, the agent)

A warrant canary is a public statement that the organization has NOT received secret government orders (NSLs, FISA warrants, gag orders, etc.). Because you can be legally compelled to LIE and say "we got nothing" --- but generally cannot be compelled to actively affirm a false statement --- the trick is: **stop signing the statement** if you ever get served. Absence of a renewed canary is the signal. The statement itself is boring; the signature and the renewal cadence are the load-bearing parts.

Three things make a canary credible:

1. **A real PGP signature** from a key whose fingerprint is published out-of-band (on the site, in commits, ideally in more than one place over time).
2. **Proof of freshness** --- a recent Bitcoin block hash embedded in the statement. The signer could not have pre-generated the signed statement before that block existed. This is what turns "signed on 2026-04-13" from a claim into a fact.
3. **Automatic expiration** --- the page visibly screams "EXPIRED --- ASSUME COMPROMISE" once the validity window passes. No human has to remember.

### Deliverables

Build all of the following. Do not skip steps, do not hand-wave. Read existing files before editing them.

#### 1. Generate the signing key (instructions, not execution)

Do NOT generate the PGP key yourself inside the agent. Print the exact commands for me to run in my own shell, because the private key must never touch your context or any AI-visible location:

```
gpg --full-generate-key
# Choose: (1) RSA and RSA, 4096 bits, key does not expire (or 2-year rotation --- your call)
# Real name: [COMPANY LLC]
# Email: [canary@example.com]
# Comment: Warrant Canary Signing Key
```

Then:

```
gpg --armor --export [canary@example.com] > [PUBLIC_ASSET_DIR]/canary-key.asc
gpg --with-colons --fingerprint [canary@example.com] | awk -F: '/^fpr:/{print $10; exit}'
```

Tell me to save the fingerprint --- we'll embed it in the canary text.

**Back up the private key offline** (paper, hardware token, encrypted USB). If the key is lost, the canary chain is broken forever and you have to start over with a new key and a published rotation notice.

#### 2. The canary text file

Create `[PUBLIC_ASSET_DIR]/canary.txt`. Plain text, ASCII, no smart quotes. Structure:

- Header with org name and "WARRANT CANARY"
- Signing identity and canonical URL
- `Issued  : YYYY-MM-DD` and `Expires : YYYY-MM-DD` lines (exact format --- the script rewrites these with sed)
- "PROOF OF FRESHNESS" section with `Block height : N` and `Block hash   : HEX` lines
- "ATTESTATIONS" section --- numbered list of negative statements the org affirms are still true:
  1. No National Security Letters received
  2. No FISA orders received
  3. No gag orders or sealed court orders
  4. Not compelled to modify, backdoor, or weaken software/crypto
  5. Not compelled to hand over keys, credentials, or infrastructure control
  6. No user data handed to government/law enforcement/intelligence
- "INTERPRETATION" section explaining: valid for the stated window, absence of renewal IS the signal, removal or alteration of any attestation IS the signal
- "VERIFICATION" section linking to:
  - `https://[example.com]/canary.txt.asc` (the detached signature)
  - `https://[example.com]/canary-key.asc` (the public key)
  - The full fingerprint in `XXXX XXXX XXXX XXXX` 4-char-group format
  - The exact verify commands: `gpg --import canary-key.asc && gpg --verify canary.txt.asc canary.txt`

Word the attestations carefully. They should be narrow, true, and enumerable. Vague language ("we respect your privacy") is useless --- you want statements that become unambiguously false the moment the thing happens.

#### 3. The renewal script

Create `scripts/renew-canary.sh`. It should:

1. Auto-detect the signing key's fingerprint via `gpg --with-colons --fingerprint [canary@example.com]` (or accept `--fingerprint` override).
2. Fetch the latest Bitcoin block height + hash from `https://mempool.space/api/blocks/tip/height` and `.../hash`. Fail loudly with a non-zero exit if either request fails.
3. Compute `Issued` = today (UTC) and `Expires` = today + 90 days. Use GNU `date -d "+90 days"` with a BSD `date -v+90d` fallback so it works on both Linux and macOS.
4. Rewrite the `Issued`, `Expires`, `Block height`, `Block hash`, and `Fingerprint` lines in `canary.txt` with `sed -i ''` (BSD) or `sed -i` (GNU) --- pick one and commit to macOS-style in-place edits if the dev is on Mac.
5. Produce the detached signature: `gpg --armor --detach-sign --yes -u [canary@example.com] --output canary.txt.asc canary.txt`
6. Immediately verify it with `gpg --verify canary.txt.asc canary.txt` and fail hard if that fails.
7. Print a "review, commit, deploy" reminder.

Make the script `set -euo pipefail`. Make it idempotent. Make it work with zero arguments in the common case.

Add a Taskfile/Makefile/npm-script entry so the user runs `task canary:renew` (or equivalent), not the raw script.

#### 4. The canary page

Build a page at `[CANARY_ROUTE]` that:

- Reads `canary.txt` at build time (do not fetch it from the client --- it must be part of the signed, deployed artifact).
- Renders the full canary text inside a monospaced `<pre>` block. Do NOT "prettify" it --- visual fidelity with the signed file is the point.
- Parses the `Expires: YYYY-MM-DD` line out of the text.
- Includes a small client-side script that compares the current date to the expiry and, if expired, unhides a bright red banner at the top of the page: **"WARNING: This canary has expired. The statement below was not renewed before its expiration date. Assume compromise."**
- Provides three download links: `canary.txt`, `canary.txt.asc`, `canary-key.asc`.
- Shows the fingerprint prominently, and the exact `gpg --import ... && gpg --verify ...` command so a technical reader can verify in 10 seconds.
- Links to this page from the site footer. This is important --- a canary no one can find might as well not exist.

#### 5. Deploy pipeline integration

- The three canary files (`canary.txt`, `canary.txt.asc`, `canary-key.asc`) must be served as **static files** at the root of the deployed site with `Content-Type: text/plain` (for `.txt` and `.asc`) or `application/pgp-signature` for the detached sig. No framework middleware between the request and the file.
- If there's a reverse proxy (Caddy, nginx), verify the files pass through cleanly. Test with `curl -I https://[example.com]/canary.txt`.
- If the site uses a CDN, make sure the canary files are NOT aggressively cached --- TTL of 5 minutes max. A stale canary from a CDN during a compromise scenario is a nightmare.
- Add the renewal step to the deploy process OR document it as a pre-deploy checklist item. A canary that's signed once and never renewed decays into worthless decoration in 90 days.

#### 6. Tests / verification

Before calling the task done:

1. Run the renewal script locally. It must produce a valid signature.
2. Run `gpg --verify canary.txt.asc canary.txt` manually. It must print `Good signature`.
3. Build the site. Visit the canary page. Confirm the text renders, the expiry banner is hidden (because it's not yet expired), and all three downloads work.
4. Temporarily change the `Expires` line to a past date and reload. Confirm the red expired banner appears. Revert.
5. Verify the page is linked from the footer.
6. `curl -sI https://[example.com]/canary.txt` after deploy and confirm 200 + correct content-type.

### Non-negotiable rules

- The private PGP key **never** touches the repo, any AI context, any cloud sync folder, or any shared machine. Only the public key gets committed.
- The canary text is ASCII only. No em dashes, smart quotes, unicode ellipsis, emoji, or non-breaking spaces. Signatures are over bytes --- subtle unicode shifts break verification.
- The statement is phrased as facts the org affirms, not promises. "We have NOT received" --- not "we will never receive". You can't promise the future; you can only refuse to lie about the present.
- The script fails loud on any error (network down, GPG missing, fingerprint mismatch). A silent canary failure is the exact failure mode a canary is supposed to defend against.
- Renewal cadence (90 days) is documented on the page itself. If users don't know how often it's supposed to renew, they can't notice when it stops.
- Do not add "co-authored by AI" or similar attributions to the canary or to commits touching it. The canary is a legal statement by the organization; authorship noise undermines it.

### What NOT to build

- No "canary dashboard" with charts. It's a text file with a signature. Keep it boring.
- No database. No API. No JavaScript framework for rendering the canary content itself. Static files only.
- No "auto-sign on CI." The signing key must stay offline on the signer's machine. CI can remind; CI does not sign.
- No multiple overlapping canaries. One canary, one signing key, one URL. Complexity is the enemy of credibility.

### Deliverable checklist (use this to self-verify)

- [ ] Public key committed to `[PUBLIC_ASSET_DIR]/canary-key.asc`
- [ ] `canary.txt` committed with all required sections
- [ ] `canary.txt.asc` committed with valid detached signature
- [ ] `scripts/renew-canary.sh` executable, idempotent, fetches BTC block, re-signs
- [ ] Taskfile/Makefile entry for renewal
- [ ] `[CANARY_ROUTE]` page renders the text, shows fingerprint, offers downloads
- [ ] Expiry-detection JS hides/shows the "EXPIRED" banner based on the `Expires` line
- [ ] Footer link to the canary page
- [ ] Private key storage plan documented (offline, backed up, known to exactly one human)
- [ ] Renewal reminder in deploy runbook or calendar

Now do the work. Read existing files before editing them. Ask me only for the bracketed values at the top --- everything else, figure out from the repo.

---

## NOTES FOR THE PERSON PASTING THIS

The original setup lives at `~/veto/scripts/renew-canary.sh`, `~/veto/site/public/veto-canary*`, and `~/veto/site/src/pages/canary.astro`. That's the reference implementation --- the prompt above is the portable recipe.

The only part that requires a human is key generation and offline backup of the private key. Everything else an agent can do from the prompt alone.
