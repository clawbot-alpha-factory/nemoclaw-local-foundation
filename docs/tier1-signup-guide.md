# Tier 1 Tool Signup Guide

Create accounts for all 10 Tier 1 tools. Use a dedicated email for NemoClaw system accounts.
Free tier for everything. No credit card required unless noted.

---

## Recommended: Create a dedicated email first

Before signing up for anything, create a dedicated email for all NemoClaw service accounts:
- Option A: Gmail — nemoclaw.system@gmail.com (or similar)
- Option B: Zoho Mail — if you already have a domain

Use this email for ALL signups below. Keeps everything separate from personal accounts.

---

## 1. Slack (Communication Hub)
**Start here — other tools will send notifications to Slack**

1. Go to https://slack.com/get-started#/createnew
2. Create workspace: "NemoClaw" (or your company name)
3. Create channels: #alerts, #approvals, #agents, #costs, #general
4. Go to https://api.slack.com/apps → Create New App → From Scratch
5. Name: "NemoClaw Bot", Workspace: your new workspace
6. Go to OAuth & Permissions → Add scopes:
   - `chat:write`, `chat:write.public`, `files:write`, `channels:read`
7. Install to Workspace → Copy **Bot User OAuth Token** (starts with `xoxb-`)
8. Go to any channel → right-click → View channel details → Copy **Channel ID** for #alerts

**Save these**:
```
SLACK_BOT_TOKEN=xoxb-your-token
SLACK_ALERTS_CHANNEL=C0123456789
```

---

## 2. HubSpot CRM (Deal Pipeline)

1. Go to https://app.hubspot.com/signup-hubspot/crm
2. Sign up with NemoClaw email → Free plan
3. Go to Settings → Integrations → Private Apps → Create private app
4. Name: "NemoClaw"
5. Scopes: `crm.objects.contacts.read`, `crm.objects.contacts.write`, `crm.objects.deals.read`, `crm.objects.deals.write`, `crm.objects.companies.read`, `crm.objects.companies.write`
6. Create app → Copy **Access Token**

**Save this**:
```
HUBSPOT_ACCESS_TOKEN=pat-na1-your-token
```

---

## 3. Apollo.io (Lead Generation)

1. Go to https://app.apollo.io/#/onboarding
2. Sign up with NemoClaw email → Free plan
3. After onboarding, go to Settings → Integrations → API Keys
4. Generate new API key → Copy it

**Save this**:
```
APOLLO_API_KEY=your-api-key
```

---

## 4. Instantly.ai (Cold Outreach)

1. Go to https://instantly.ai/app/sign-up
2. Sign up with NemoClaw email
3. Note: Free trial gives limited access. Growth plan ($30/mo) needed for API
4. After signup, go to Settings → Integrations → API Key
5. Copy API key

**Save this**:
```
INSTANTLY_API_KEY=your-api-key
```

**Note**: Instantly requires a paid plan for API access. Start with the dashboard manually, upgrade when ready to automate.

---

## 5. Resend (Transactional Email)

1. Go to https://resend.com/signup
2. Sign up with NemoClaw email → Free plan (3K emails/month)
3. Go to API Keys → Create API key
4. Name: "NemoClaw" → Full access → Create
5. Copy the API key (shown only once)

**Save this**:
```
RESEND_API_KEY=re_your-api-key
```

---

## 6. Supabase (Database + Auth + Storage)

1. Go to https://supabase.com/dashboard/sign-up
2. Sign up with GitHub or NemoClaw email → Free plan
3. Create new project: "nemoclaw-production"
4. Choose region closest to you (e.g., Frankfurt for Middle East)
5. Set a strong database password → Save it
6. After project creates, go to Settings → API
7. Copy: **Project URL** and **anon public key** and **service_role secret key**

**Save these**:
```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=eyJ...your-anon-key
SUPABASE_SERVICE_KEY=eyJ...your-service-key
```

---

## 7. Lemon Squeezy (Payments)

1. Go to https://app.lemonsqueezy.com/register
2. Sign up with NemoClaw email
3. Complete onboarding (store name, etc.)
4. Go to Settings → API → Create API key
5. Copy the API key

**Save this**:
```
LEMONSQUEEZY_API_KEY=your-api-key
```

**Note**: To receive payouts, connect Payoneer in Settings → Payouts (Jordan-compatible).

---

## 8. n8n (Workflow Automation — Self-Hosted)

No account needed — self-hosted on your MacBook.

```bash
# Install via npm (already have Node.js)
npm install -g n8n

# Start n8n
n8n start
```

Opens at http://localhost:5678
Create an admin account on first visit.

Then enable the API:
1. Go to Settings → API → Enable API
2. Create API key → Copy it

**Save this**:
```
N8N_API_KEY=your-api-key
N8N_BASE_URL=http://localhost:5678
```

---

## 9. Google Ads API (Ads Management)

1. Go to https://ads.google.com/home/tools/manager-accounts/
2. Create a Google Ads Manager account (use NemoClaw email)
3. Go to https://console.cloud.google.com/
4. Create project: "nemoclaw-ads"
5. Enable "Google Ads API"
6. Create OAuth 2.0 credentials (Desktop app type)
7. Download the client secret JSON
8. Apply for a developer token: Google Ads → Tools → API Center
   - Basic access is fine for testing

**Save these**:
```
GOOGLE_ADS_DEVELOPER_TOKEN=your-dev-token
GOOGLE_ADS_CLIENT_ID=your-client-id
GOOGLE_ADS_CLIENT_SECRET=your-client-secret
GOOGLE_ADS_CUSTOMER_ID=your-customer-id
```

**Note**: Developer token approval takes 1-3 days. Start the application now, build integration while waiting.

---

## 10. Meta Ads API (Facebook + Instagram Ads)

1. Go to https://developers.facebook.com/
2. Sign up / log in with a Facebook account
3. Create App → Business type → Name: "NemoClaw"
4. Add "Marketing API" product
5. Go to Settings → Basic → Copy **App ID** and **App Secret**
6. Go to Tools → Graph API Explorer
7. Select your app → Generate User Token with permissions:
   - `ads_management`, `ads_read`, `business_management`
8. Copy the access token

**Save these**:
```
META_APP_ID=your-app-id
META_APP_SECRET=your-app-secret
META_ACCESS_TOKEN=your-access-token
```

**Note**: Long-lived tokens expire in 60 days. Production apps need Business Verification for permanent tokens.

---

## After All Signups — Add to .env

Add all keys to your NemoClaw config:

```bash
cd ~/nemoclaw-local-foundation
cat >> config/.env << 'EOF'

# ── Tier 1 External Tools ──
SLACK_BOT_TOKEN=xoxb-your-token
SLACK_ALERTS_CHANNEL=C0123456789
HUBSPOT_ACCESS_TOKEN=pat-na1-your-token
APOLLO_API_KEY=your-api-key
INSTANTLY_API_KEY=your-api-key
RESEND_API_KEY=re_your-api-key
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=eyJ...your-anon-key
SUPABASE_SERVICE_KEY=eyJ...your-service-key
LEMONSQUEEZY_API_KEY=your-api-key
N8N_API_KEY=your-api-key
N8N_BASE_URL=http://localhost:5678
GOOGLE_ADS_DEVELOPER_TOKEN=your-dev-token
GOOGLE_ADS_CLIENT_ID=your-client-id
GOOGLE_ADS_CLIENT_SECRET=your-client-secret
GOOGLE_ADS_CUSTOMER_ID=your-customer-id
META_APP_ID=your-app-id
META_APP_SECRET=your-app-secret
META_ACCESS_TOKEN=your-access-token
EOF
```

Then load them:
```bash
set -a && source config/.env && set +a
```

---

## Signup Order (Recommended)

Do them in this order — each builds on the previous:

| # | Tool | Time | Depends On |
|---|---|---|---|
| 1 | Slack | 5 min | Nothing |
| 2 | HubSpot | 5 min | Nothing |
| 3 | Apollo.io | 5 min | Nothing |
| 4 | Resend | 3 min | Nothing |
| 5 | Supabase | 5 min | Nothing |
| 6 | Lemon Squeezy | 5 min | Nothing |
| 7 | n8n | 3 min | Node.js (already have) |
| 8 | Instantly.ai | 5 min | Nothing (API needs paid plan) |
| 9 | Google Ads API | 10 min | Google account (dev token takes days) |
| 10 | Meta Ads API | 10 min | Facebook account |

**Total estimated time: ~55 minutes**

---

## What I Build After Each Signup

As you complete each signup and paste the API key, I'll build:

1. **Slack**: `slack_bridge.py` — send alerts, approvals, status updates
2. **HubSpot**: `hubspot_bridge.py` — contacts, deals, companies CRUD
3. **Apollo.io**: `apollo_bridge.py` — people search, company enrichment
4. **Resend**: `resend_bridge.py` — send transactional emails
5. **Supabase**: `supabase_bridge.py` — database, auth, storage
6. **Lemon Squeezy**: `lemonsqueezy_bridge.py` — products, checkouts, subscriptions
7. **n8n**: `n8n_bridge.py` — trigger workflows, manage executions
8. **Instantly.ai**: `instantly_bridge.py` — campaigns, leads, analytics
9. **Google Ads**: `google_ads_bridge.py` — campaigns, keywords, reporting
10. **Meta Ads**: `meta_ads_bridge.py` — campaigns, audiences, creatives

Each bridge follows the PinchTabClient pattern: tuple returns, rate limiting, action logging, error handling, 20+ tests.
