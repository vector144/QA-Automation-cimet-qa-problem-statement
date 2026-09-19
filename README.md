# CIMET QA Automation Platform
### AI That Listens to Every Sales Call — So Humans Don't Have To

---

## The Problem

Every day, CIMET's agents make hundreds of phone calls to sell internet and energy plans to customers.

Before a sale can go through, agents **must** say certain things on every call — by law:
- Disclose that the call is being recorded
- Quote the correct price (exactly as it appears in the system)
- Read the terms and conditions
- Confirm the customer's identity
- Mute the recording before taking card details

Right now, a small QA team **manually listens to 1–3% of calls** to check these. That means **97 out of every 100 calls go unchecked**. If an agent quotes the wrong price or skips a legal disclosure — nobody catches it. That's a compliance breach, a potential fine, and an unhappy customer.

---

## What I Built

A system that **automatically listens to 100% of calls** and checks every rule — in seconds, not hours.

Think of it as a **robot QA auditor** that:

1. 🎙️ **Listens to the call recording** using AI (Groq Whisper)
2. 📝 **Reads the transcript** and separates what the agent said from what the customer said
3. ✅ **Checks every rule** — did they say the right price? Did they read the disclaimer?
4. 🚦 **Makes a decision** — PASS the sale, FAIL it, or flag it for a human to review
5. 📍 **Shows exactly where** in the call something went wrong — down to the second

---

## Real Example From a Real Call

> Agent said: **"$35.90 for the first six months"**
> System price: **$42.90**
> Result: ❌ **SALE BLOCKED**

The system caught a $7 pricing mistake that could have led to a customer complaint, a clawback, or a regulatory fine — automatically, without anyone having to listen to 14 minutes of audio.

---

## How It Works (In Simple Terms)

```
Call Recording
      |
      | AI listens and creates a transcript
      v
 Who said what, and when?
      |
      | Check every rule automatically
      v
 Did the agent say the right things?
 Did the price match the system?
 Were there any long silences?
      |
      v
 PASSED — Sale goes through  ✅
 FAILED — Sale is held       ❌
 REVIEW — Human takes a look 👀
```

---

## The Dashboard

A web app for QA reviewers where they can:

- **See every call** and its compliance result at a glance
- **Click on any failed check** and the audio automatically plays from that exact moment
- **Read the agent's exact words** that caused the failure
- **Override a result** if the AI got it wrong (with a mandatory reason logged)
- **Export reports** for retailers and management

---

## What the AI Checks (3 Types)

| Check Type | What It Looks For | Blocks the Sale? |
|------------|------------------|-----------------|
| **Script Compliance** | Did the agent say the required legal phrases? | Yes |
| **Price & Details** | Do the quoted numbers match what's in the system? | Yes |
| **Call Quality** | Were there awkward silences? Did the call flow well? | No (coaching only) |

---

## Results on Real Calls

Tested on **2 real CIMET call recordings** (each ~14 minutes long):

| Call | AI Score | Result | Issues Found |
|------|---------|--------|-------------|
| Call 3613793 | 75 / 100 | ❌ FAILED | Wrong intro price quoted |
| Call 3613794 | 75 / 100 | ❌ FAILED | Same pricing error |

Both calls had the **same agent quoting $35.90 instead of $42.90**. Since this happened twice, the system also **automatically flagged this as a repeat offence** and would alert the Team Leader.

---

## Why This Matters

| Before | After |
|--------|-------|
| 1–3% of calls checked | 100% of calls checked |
| Results in days | Results in 30 seconds |
| Manual listening | AI + instant transcript |
| Easy to miss errors | Every mismatch caught |
| No record of why | Full audit trail, every decision logged |

---

## Built in 12 Hours — Solo

This was submitted as a solo entry for the **CIMET Engineering Hackathon, Jaipur**.

**AI Tools Used:**
- 🎤 **Groq Whisper** — transcribes audio 10x faster than real-time
- 🧠 **Claude (Anthropic)** — understands what the agent said and checks it against the rules
- ⚡ **FastAPI** — the backend that runs everything
- 🖥️ **React** — the dashboard that QA reviewers use

---

*No sale ships unscored. And now you know exactly why — in seconds, not minutes.*
