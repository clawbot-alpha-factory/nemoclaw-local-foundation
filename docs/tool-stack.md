# NemoClaw External Tool Stack

Complete registry of all external tools integrated or planned for the NemoClaw system.
58 tools across 28 categories. Free tier used for each until upgrade is required.

**Created**: 2026-03-28
**Status**: Tier 1 in progress, Tiers 2-5 planned

---

## Integration Status Legend

| Status | Meaning |
|---|---|
| ✅ Connected | Integrated and working |
| 🔧 Tier 1 | Building now — revenue pipeline |
| 📋 Tier 2 | Next — content & intelligence |
| 📋 Tier 3 | Engineering & building |
| 📋 Tier 4 | AI SaaS infrastructure |
| 📋 Tier 5 | Scale & optimize |

---

## 1. Lead Generation & Enrichment

| Tool | Free Tier | Agent | Status | Integration |
|---|---|---|---|---|
| **Apollo.io** | 10K records/month, 5 email credits/day | growth_revenue_lead | 🔧 Tier 1 | REST API |

**What it enables**: B2B lead search by company, role, industry. Contact emails, phone numbers, org charts, company data. Enrichment of existing leads with firmographics and technographics.

**API Docs**: https://apolloio.github.io/apollo-api-docs/
**Key Endpoints**: People Search, Company Enrichment, Contact Enrichment, People Enrichment
**Auth**: API key in header

---

## 2. Cold Outreach & Email

| Tool | Free Tier | Agent | Status | Integration |
|---|---|---|---|---|
| **Instantly.ai** | Free trial → $30/mo | growth_revenue_lead | 🔧 Tier 1 | REST API |
| **Resend** | 3K emails/month, 100/day | operations_systems_lead | 🔧 Tier 1 | REST API |

**Instantly.ai** — Cold email sequences with built-in warmup, deliverability monitoring, A/B testing, campaign analytics. Unlimited email accounts. Best-in-class deliverability engine.

**API Docs**: https://developer.instantly.ai/
**Key Endpoints**: Campaigns, Leads, Accounts, Analytics
**Auth**: API key

**Resend** — Modern transactional email API. Product emails (receipts, notifications, password resets). React email template support. Not for cold outreach.

**API Docs**: https://resend.com/docs/api-reference
**Key Endpoints**: Send Email, Domains, API Keys
**Auth**: API key in Authorization header

---

## 3. Web Scraping & Data

| Tool | Free Tier | Agent | Status | Integration |
|---|---|---|---|---|
| **Apify** | $5/month free credit | intelligence_research_lead | 📋 Tier 2 | REST API |
| **SerpAPI** | 100 searches/month | intelligence_research_lead | 📋 Tier 2 | REST API |
| **PinchTab** | Free (local) | all web-enabled agents | ✅ Connected | HTTP localhost:9867 |

**Apify** — Platform with 400+ pre-built scrapers (actors). One integration covers Instagram, TikTok, Reddit, LinkedIn, Twitter/X, Google Maps, YouTube scraping. Proxy rotation and anti-detection built in.

**API Docs**: https://docs.apify.com/api/v2
**Key Actors**: Instagram Scraper, TikTok Scraper, Reddit Scraper, Twitter Scraper, LinkedIn Scraper, Google Maps Scraper, YouTube Scraper
**Auth**: API token

**SerpAPI** — Google search results as structured JSON. Also supports Bing, YouTube, Google Maps, Google Shopping, Google Scholar, Apple App Store, Google Play.

**API Docs**: https://serpapi.com/search-api
**Auth**: API key as query parameter

**PinchTab** — 12MB Go binary for direct Chrome control. Accessibility-first element refs. ~800 tokens/page text extraction. Multi-instance with isolated profiles.

**Docs**: https://pinchtab.com/docs/
**Bridge**: `scripts/web_browser.py` (40/40 tests)
**Config**: `config/pinchtab-config.yaml`

---

## 4. Workflow Automation

| Tool | Free Tier | Agent | Status | Integration |
|---|---|---|---|---|
| **n8n** | Free forever (self-hosted) | operations_systems_lead | 🔧 Tier 1 | Self-hosted + REST API |

**What it enables**: Visual workflow builder with 400+ integrations. Connect any tool to any tool. Webhooks for receiving events. Cron for scheduled jobs. Full control with self-hosting — no vendor lock-in, no workflow limits.

**Install**: `npx n8n` or Docker
**API Docs**: https://docs.n8n.io/api/
**Key Features**: Webhook triggers, HTTP requests, code nodes (JavaScript/Python), error handling, sub-workflows
**Auth**: API key or Basic auth

---

## 5. Backend & Database

| Tool | Free Tier | Agent | Status | Integration |
|---|---|---|---|---|
| **Supabase** | 500MB DB, 1GB storage, 50K MAU | operations_systems_lead | 🔧 Tier 1 | REST API + Client SDK |
| **Upstash** | 10K commands/day | operations_systems_lead | 📋 Tier 4 | REST API |

**Supabase** — PostgreSQL database + auth + file storage + edge functions + realtime subscriptions in one platform. Replaces separate database, auth, storage, and serverless function providers.

**API Docs**: https://supabase.com/docs/guides/api
**Key Features**: Row-level security, auto-generated REST API, real-time subscriptions, edge functions, storage buckets
**Auth**: anon key + service role key
**Python SDK**: `pip install supabase`

**Upstash** — Serverless Redis for caching, rate limiting, and job queues. Pay-per-request pricing. REST API (no persistent connection needed).

**API Docs**: https://upstash.com/docs/redis/overall/getstarted
**Key Features**: Redis commands via REST, Kafka topics, QStash (message queue)
**Auth**: REST token

---

## 6. Payment Processing

| Tool | Free Tier | Agent | Status | Integration |
|---|---|---|---|---|
| **Lemon Squeezy** | No monthly fee, 5%+50¢ per transaction | growth_revenue_lead | 🔧 Tier 1 | REST API + Webhooks |

**What it enables**: Merchant of record — handles global sales tax, VAT, compliance automatically. Subscriptions, one-time payments, license keys, digital products. Jordan-compatible (Payoneer payout).

**API Docs**: https://docs.lemonsqueezy.com/api
**Key Endpoints**: Products, Variants, Checkouts, Subscriptions, Orders, Webhooks
**Auth**: API key in Authorization header
**Webhooks**: subscription_created, order_created, subscription_updated, etc.

---

## 7. CRM

| Tool | Free Tier | Agent | Status | Integration |
|---|---|---|---|---|
| **HubSpot CRM** | Unlimited contacts, deal pipeline | growth_revenue_lead | 🔧 Tier 1 | REST API |

**What it enables**: Contact management, deal tracking, email logging, meeting scheduler, forms, lead scoring. Connects Apollo leads → HubSpot pipeline → Instantly outreach → Lemon Squeezy revenue.

**API Docs**: https://developers.hubspot.com/docs/api/overview
**Key Endpoints**: Contacts, Companies, Deals, Engagements, Pipelines
**Auth**: Private app access token
**Python SDK**: `pip install hubspot-api-client`

---

## 8. Project & Task Management

| Tool | Free Tier | Agent | Status | Integration |
|---|---|---|---|---|
| **Asana** | Free (15 users, unlimited tasks) | operations_systems_lead | ✅ Connected | REST API |
| **Linear** | Free (small teams) | engineering_lead | 📋 Tier 3 | GraphQL API |

**Asana** — Business operations and agent task tracking. Already connected with ASANA_ACCESS_TOKEN.

**Linear** — Developer-focused issue tracking with cycles, roadmaps, and GitHub integration. For engineering sprints and code work.

**API Docs**: https://developers.linear.app/docs
**Auth**: API key or OAuth

---

## 9. Communication

| Tool | Free Tier | Agent | Status | Integration |
|---|---|---|---|---|
| **Slack** | Free (90-day history, 10 integrations) | all agents | 🔧 Tier 1 | REST API + Webhooks |
| **Telegram Bot API** | Free | executive_operator | 📋 Tier 2 | Bot API |

**Slack** — Team workspace for agent alerts, approval notifications, status updates, error reporting. Webhook for incoming, Bot API for interactive messages.

**API Docs**: https://api.slack.com/
**Key Features**: Incoming webhooks, slash commands, interactive messages, file uploads
**Auth**: Bot token (xoxb-)

**Telegram Bot API** — Personal mobile alerts. Quick approve/reject commands. System status on the go.

**API Docs**: https://core.telegram.org/bots/api
**Auth**: Bot token from @BotFather

---

## 10. Analytics & Monitoring

| Tool | Free Tier | Agent | Status | Integration |
|---|---|---|---|---|
| **PostHog** | 1M events/month | operations_systems_lead | 📋 Tier 3 | REST API + JS SDK |
| **Sentry** | 5K errors/month | engineering_lead | 📋 Tier 3 | SDK |
| **Better Stack** | 10 monitors | operations_systems_lead | 📋 Tier 3 | REST API |

**PostHog** — Product analytics + session replay + feature flags in one. Replaces Mixpanel + LaunchDarkly. Self-hostable.

**Sentry** — Error tracking and performance monitoring. Catches crashes, slow queries, failed API calls.

**Better Stack** — Uptime monitoring + status pages + incident management. Alerts when services go down.

---

## 11. Social Media Management

| Tool | Free Tier | Agent | Status | Integration |
|---|---|---|---|---|
| **Buffer** | 3 channels, 10 posts/channel/month | narrative_content_lead | 📋 Tier 2 | REST API |
| **PinchTab** | Free (local) | narrative_content_lead | ✅ Connected | HTTP localhost:9867 |

**Buffer** — Multi-platform scheduling (LinkedIn, X, Instagram, TikTok, Facebook). Analytics per post. Optimal timing suggestions.

**API Docs**: https://buffer.com/developers/api
**Auth**: OAuth 2.0

---

## 12. SEO & Content Intelligence

| Tool | Free Tier | Agent | Status | Integration |
|---|---|---|---|---|
| **Google Search Console** | Free | narrative_content_lead | 📋 Tier 2 | REST API |
| **Ubersuggest** | 3 searches/day | narrative_content_lead | 📋 Tier 2 | Web (via PinchTab) |

**Google Search Console** — First-party Google data: actual search queries, click-through rates, indexing status, crawl errors. No third-party tool can replicate this data.

**API Docs**: https://developers.google.com/webmaster-tools/v1/api_reference_index
**Auth**: OAuth 2.0

**Ubersuggest** — Keyword research, competitor domain analysis, site audit, content ideas. Access via PinchTab browser automation.

---

## 13. AI & LLM Providers

| Tool | Free Tier | Agent | Status | Integration |
|---|---|---|---|---|
| **Anthropic** | Pay per use | all agents | ✅ Connected | API via LangChain |
| **OpenAI** | Pay per use | all agents | ✅ Connected | API via LangChain |
| **Google** | Pay per use | all agents | ✅ Connected | API via LangChain |
| **Groq** | Free tier | all agents | 📋 Tier 5 | REST API |
| **OpenRouter** | Pay per use | all agents | 📋 Tier 5 | REST API |
| **Ollama** | Free (local) | all agents | 📋 Tier 3 | Local HTTP API |

**Groq** — Ultra-fast inference for open-source models (Llama, Mixtral). 10x faster than OpenAI for compatible models. Use for high-volume, low-cost tasks.

**API Docs**: https://console.groq.com/docs/quickstart
**Auth**: API key

**OpenRouter** — Unified API to 100+ models across all providers. Automatic fallback if one provider is down. Single API key for everything.

**API Docs**: https://openrouter.ai/docs
**Auth**: API key

**Ollama** — Run Llama, Mistral, Phi, Gemma locally on M1 for zero-cost development and testing. REST API compatible with OpenAI format.

**Install**: `curl -fsSL https://ollama.com/install.sh | sh`
**API**: http://localhost:11434/api

---

## 14. AI Observability

| Tool | Free Tier | Agent | Status | Integration |
|---|---|---|---|---|
| **LangSmith** | 5K traces/month | operations_systems_lead | 📋 Tier 3 | Python SDK |
| **Helicone** | 100K requests/month | operations_systems_lead | 📋 Tier 4 | Proxy (header change) |

**LangSmith** — LLM tracing, prompt evaluation, dataset management. Made by LangChain team. See every step of every chain/graph execution.

**Docs**: https://docs.smith.langchain.com/
**Auth**: API key

**Helicone** — LLM proxy that sits between your code and the LLM provider. Adds cost tracking, caching, rate limiting, retries. One header change to enable.

**Docs**: https://docs.helicone.ai/
**Auth**: API key (added as header to existing LLM calls)

---

## 15. Email Infrastructure

| Tool | Free Tier | Agent | Status | Integration |
|---|---|---|---|---|
| **Zoho Mail** | Free (5 users) | all agents | 📋 Tier 2 | IMAP/SMTP + API |
| **Gmail** | Free (15GB) | all agents | ✅ Connected | MCP |

**Zoho Mail** — Free business email (you@yourdomain.com). 5 users, 5GB/user. Custom domain, admin console, mobile apps.

**Setup**: https://www.zoho.com/mail/help/adminconsole/
**API Docs**: https://www.zoho.com/mail/help/api/

---

## 16. File Storage

| Tool | Free Tier | Agent | Status | Integration |
|---|---|---|---|---|
| **Cloudflare R2** | 10GB/month, zero egress | operations_systems_lead | 📋 Tier 3 | S3-compatible API |
| **Google Drive** | 15GB | all agents | ✅ Connected | MCP |

**Cloudflare R2** — S3-compatible object storage with zero egress fees. Store artifacts, exports, reports, media files.

**Docs**: https://developers.cloudflare.com/r2/
**Auth**: Access key + secret (S3 API) or Cloudflare API token

---

## 17. Hosting & Deployment

| Tool | Free Tier | Agent | Status | Integration |
|---|---|---|---|---|
| **Vercel** | Hobby plan (free) | engineering_lead | 📋 Tier 3 | CLI + REST API |
| **Railway** | $5 free credit | engineering_lead | 📋 Tier 3 | CLI + REST API |

**Vercel** — Frontend hosting. Next.js optimized. Preview deployments per PR. Edge functions. Analytics.

**Docs**: https://vercel.com/docs
**CLI**: `npm i -g vercel`

**Railway** — Backend hosting. PostgreSQL, Redis, cron jobs, workers. One-click deploy from GitHub. Logs, metrics, scaling.

**Docs**: https://docs.railway.app/
**CLI**: `npm i -g @railway/cli`

---

## 18. Domain & DNS

| Tool | Free Tier | Agent | Status | Integration |
|---|---|---|---|---|
| **Cloudflare** | Free plan | operations_systems_lead | 📋 Tier 3 | REST API |
| **Namecheap** | ~$10/year per domain | operations_systems_lead | 📋 Tier 3 | Manual |

**Cloudflare** — DNS, CDN, DDoS protection, SSL, firewall rules, page rules, Workers, R2. One platform for all web infrastructure.

**API Docs**: https://developers.cloudflare.com/api/
**Auth**: API token

---

## 19. Ads Management

| Tool | Free Tier | Agent | Status | Integration |
|---|---|---|---|---|
| **Google Ads API** | Free API (pay for ads) | growth_revenue_lead | 🔧 Tier 1 | REST API |
| **Meta Ads API** | Free API (pay for ads) | growth_revenue_lead | 🔧 Tier 1 | REST API |
| **TikTok Ads API** | Free API (pay for ads) | growth_revenue_lead | 📋 Tier 5 | REST API |
| **Google Looker Studio** | Free | intelligence_research_lead | 📋 Tier 2 | Data connectors |

**Google Ads API** — Full programmatic control over Google Ads campaigns. Create campaigns, ad groups, keywords, ads. Set bids, budgets. Pull performance reports.

**Docs**: https://developers.google.com/google-ads/api/docs/start
**Auth**: OAuth 2.0 + Developer token
**Python SDK**: `pip install google-ads`

**Meta Ads API** — Facebook + Instagram ad management. Campaign creation, audience targeting, creative upload, pixel tracking, conversion API.

**Docs**: https://developers.facebook.com/docs/marketing-apis
**Auth**: Access token via Facebook App
**Python SDK**: `pip install facebook-business`

**TikTok Ads API** — Campaign management, audience creation, creative upload, event tracking.

**Docs**: https://business-api.tiktok.com/portal/docs
**Auth**: Access token

**Google Looker Studio** — Free dashboarding that connects to Google Ads, Meta Ads, Google Analytics, Google Sheets, BigQuery. Unified reporting across all ad platforms.

---

## 20. Social Media Scrapers

| Tool | Free Tier | Agent | Status | Integration |
|---|---|---|---|---|
| **Apify** (all scrapers) | $5/month credit | intelligence_research_lead | 📋 Tier 2 | REST API |
| **Reddit API** (official) | Free (100 req/min) | intelligence_research_lead | 📋 Tier 2 | REST API |

**Apify Scrapers** — One platform, one API key, one integration for all social scraping:

| Actor | What It Scrapes |
|---|---|
| Instagram Scraper | Profiles, posts, reels, stories, hashtags, comments, followers |
| TikTok Scraper | Videos, profiles, hashtags, trending sounds, comments |
| Reddit Scraper | Posts, comments, subreddits, user history, search results |
| Twitter/X Scraper | Tweets, profiles, followers, search, trending |
| LinkedIn Scraper | Company pages, people profiles, job listings |
| Google Maps Scraper | Business listings, reviews, contact info, opening hours |
| YouTube Scraper | Videos, channels, comments, playlists, search results |

**API Docs**: https://docs.apify.com/api/v2
**Auth**: API token

**Reddit API** — Official API with higher rate limits and real-time access. Better for monitoring subreddits, tracking mentions, and building Reddit bots.

**Docs**: https://www.reddit.com/dev/api/
**Auth**: OAuth 2.0 (client ID + secret)

---

## 21. AI SaaS Building Blocks

| Tool | Free Tier | Agent | Status | Integration |
|---|---|---|---|---|
| **LangChain** | Free | all agents | ✅ Connected | Python SDK |
| **LangGraph** | Free | all agents | ✅ Connected | Python SDK |
| **Pinecone** | 100K vectors free | engineering_lead | 📋 Tier 3 | REST API + Python SDK |
| **Unstructured.io** | Free (OSS) | engineering_lead | 📋 Tier 3 | Python library |
| **Instructor** | Free | engineering_lead | 📋 Tier 3 | Python library |

**Pinecone** — Managed vector database for embeddings and RAG. Store document chunks as vectors, query by semantic similarity. Zero-ops.

**Docs**: https://docs.pinecone.io/
**Python SDK**: `pip install pinecone-client`
**Auth**: API key

**Unstructured.io** — Parse any document (PDF, DOCX, HTML, PPTX, images, emails) into clean structured text. Essential for RAG pipelines.

**Install**: `pip install unstructured`

**Instructor** — Extract structured data from LLM responses using Pydantic models. Guarantees JSON schema compliance from any LLM.

**Install**: `pip install instructor`

---

## 22. SaaS Infrastructure

| Tool | Free Tier | Agent | Status | Integration |
|---|---|---|---|---|
| **Clerk** | 10K MAU free | engineering_lead | 📋 Tier 4 | REST API + SDK |
| **Knock** | 10K messages free | engineering_lead | 📋 Tier 4 | REST API + SDK |
| **Crisp** | Free (2 seats) | narrative_content_lead | 📋 Tier 4 | REST API + Widget |

**Clerk** — Authentication and user management. Social login, email/password, MFA, organizations, user profiles, session management. Better DX than Auth0.

**Docs**: https://clerk.com/docs
**Auth**: Secret key

**Knock** — Multi-channel notification infrastructure. Send email + push + in-app + SMS from one API call. User preferences, digest batching, templates.

**Docs**: https://docs.knock.app/
**Auth**: API key

**Crisp** — Live chat + helpdesk + knowledge base. Embed chat widget on product. Support inbox for customer conversations. Chatbot for auto-responses.

**Docs**: https://docs.crisp.chat/
**Auth**: API token

---

## 23. Terminal & CLI Tools

| Tool | What It Does | Install |
|---|---|---|
| **tmux** | Terminal multiplexing, persistent sessions | `brew install tmux` |
| **jq** | JSON processing in terminal | `brew install jq` |
| **yq** | YAML processing in terminal | `brew install yq` |
| **ripgrep** | Ultra-fast recursive code search | `brew install ripgrep` |
| **lazygit** | Terminal UI for git operations | `brew install lazygit` |
| **gh** | GitHub CLI (PRs, issues, releases) | `brew install gh` |
| **direnv** | Auto-load .env per directory | `brew install direnv` |
| **Claude Code** | Agentic coding from terminal | Anthropic product |

All free, all installed via Homebrew. One command to install all:
```bash
brew install tmux jq yq ripgrep lazygit gh direnv
```

---

## 24. Website & Landing Pages

| Tool | Free Tier | Agent | Status | Integration |
|---|---|---|---|---|
| **Next.js + Vercel** | Free (hobby) | engineering_lead | 📋 Tier 3 | CLI |
| **Framer** | Free (1 site) | narrative_content_lead | 📋 Tier 3 | Visual editor |

**Next.js** — React framework for the product application. Server rendering, API routes, app router, middleware.

**Framer** — Visual website builder for marketing sites and landing pages. Faster than coding for non-technical content pages. CMS built in.

---

## 25. Video & Audio Production

| Tool | Free Tier | Agent | Status | Integration |
|---|---|---|---|---|
| **ElevenLabs** | 10K chars/month | narrative_content_lead | 📋 Tier 5 | REST API |
| **HeyGen** | Free trial | narrative_content_lead | 📋 Tier 5 | REST API |
| **Whisper** | Free (local) | narrative_content_lead | 📋 Tier 3 | Python library |

**ElevenLabs** — AI voice synthesis and voice cloning. Generate voiceovers for video scripts. 29 languages.

**Docs**: https://docs.elevenlabs.io/
**Auth**: API key

**HeyGen** — AI avatar videos from text scripts. No camera, no editing. Product demos, tutorials, social content.

**Docs**: https://docs.heygen.com/
**Auth**: API key

**Whisper** — OpenAI's speech-to-text model. Run locally for free. Transcribe meetings, calls, podcasts.

**Install**: `pip install openai-whisper`

---

## 26. Image & Design

| Tool | Free Tier | Agent | Status | Integration |
|---|---|---|---|---|
| **DALL-E** | Pay per image | narrative_content_lead | ✅ Connected | OpenAI API |
| **Canva** | Free tier | narrative_content_lead | 📋 Tier 2 | REST API |
| **Cloudinary** | 25 credits/month | engineering_lead | 📋 Tier 3 | REST API + SDK |

**Canva** — Templates for social graphics, presentations, ads, thumbnails. API allows programmatic design generation.

**Docs**: https://www.canva.dev/docs/connect/
**Auth**: API key

**Cloudinary** — Image and video CDN with on-the-fly transformations (resize, crop, watermark, format conversion, optimization). Auto-responsive images.

**Docs**: https://cloudinary.com/documentation
**Auth**: Cloud name + API key + secret

---

## 27. Legal & Compliance

| Tool | Free Tier | Agent | Status | Integration |
|---|---|---|---|---|
| **Termly** | Free (basic) | operations_systems_lead | 📋 Tier 4 | Embed code |

**What it enables**: Privacy policy generator, terms of service generator, cookie consent banner. Auto-updates when laws change. GDPR, CCPA, CalOPPA compliant.

**Docs**: https://termly.io/resources/

---

## 28. Calendar & Scheduling

| Tool | Free Tier | Agent | Status | Integration |
|---|---|---|---|---|
| **Google Calendar** | Free | all agents | ✅ Connected | MCP |
| **Cal.com** | Free (1 user) | growth_revenue_lead | 📋 Tier 2 | REST API |

**Cal.com** — Open-source Calendly alternative. Booking links, availability management, round-robin, team scheduling. Self-hostable.

**Docs**: https://cal.com/docs/enterprise-features/api
**Auth**: API key

---

## Tier Breakdown

### Tier 1 — Revenue Pipeline (connect first)
| Tool | Category |
|---|---|
| Apollo.io | Lead generation |
| HubSpot CRM | CRM |
| Instantly.ai | Cold outreach |
| Resend | Transactional email |
| Supabase | Database + auth + storage |
| Lemon Squeezy | Payments |
| n8n | Workflow automation |
| Slack | Communication |
| Google Ads API | Ads management |
| Meta Ads API | Ads management |

### Tier 2 — Content & Intelligence
| Tool | Category |
|---|---|
| Buffer | Social management |
| Google Search Console | SEO |
| Ubersuggest | SEO |
| Apify | Social scrapers |
| SerpAPI | Search data |
| Reddit API | Social intelligence |
| Telegram Bot | Mobile alerts |
| Zoho Mail | Business email |
| Canva | Design |
| Cal.com | Scheduling |
| Google Looker Studio | Ads reporting |

### Tier 3 — Engineering & Building
| Tool | Category |
|---|---|
| Vercel | Frontend hosting |
| Railway | Backend hosting |
| Cloudflare | DNS + CDN + R2 |
| Linear | Issue tracking |
| PostHog | Analytics |
| Sentry | Error tracking |
| Better Stack | Uptime monitoring |
| Ollama | Local LLMs |
| Pinecone | Vector database |
| Unstructured.io | Document parsing |
| Instructor | Structured LLM output |
| LangSmith | LLM tracing |
| Cloudinary | Image CDN |
| Whisper | Transcription |
| Next.js + Framer | Websites |

### Tier 4 — AI SaaS Infrastructure
| Tool | Category |
|---|---|
| Clerk | Auth |
| Knock | Notifications |
| Crisp | Live chat + support |
| Helicone | LLM cost control |
| Upstash | Redis caching |
| Termly | Legal compliance |

### Tier 5 — Scale & Optimize
| Tool | Category |
|---|---|
| Groq | Fast inference |
| OpenRouter | Multi-model routing |
| TikTok Ads API | Ads |
| ElevenLabs | Voice synthesis |
| HeyGen | AI video |

---

## Integration Architecture

All external tools connect to NemoClaw through one of these patterns:

### Pattern A: Direct API Bridge (like web_browser.py)
```
Skill → Python Bridge → External API → Response → Skill
```
Used for: Apollo, HubSpot, Instantly, Resend, Lemon Squeezy, Slack, Buffer

### Pattern B: n8n Workflow Trigger
```
NemoClaw Event → n8n Webhook → n8n Workflow → External Tools → n8n Response → NemoClaw
```
Used for: Multi-tool workflows, scheduled jobs, event-driven automations

### Pattern C: PinchTab Browser
```
Skill → PinchTabClient → Chrome → Website → Text/Snapshot → Skill
```
Used for: Ubersuggest, Google Search Console, Looker Studio, any tool without API

### Pattern D: SDK Integration
```
Skill → Python SDK → External Service → Response → Skill
```
Used for: Supabase, Pinecone, Sentry, PostHog, LangSmith

### Governance
All external tool calls governed by:
- **MA-19**: Access control — which agents can use which tools
- **MA-8**: Behavior rules — safety checks on external actions
- **MA-6**: Cost tracking — per-agent external tool spend
- **MA-14**: Health monitoring — external service availability
- **MA-16**: Human approval — required for destructive or financial actions

---

## Already Connected (8 tools)

| Tool | How | Since |
|---|---|---|
| Anthropic (Claude) | API via LangChain | Phase 1 |
| OpenAI (GPT-4o) | API via LangChain | Phase 1 |
| Google (Gemini) | API via LangChain | Phase 1 |
| Asana | REST API (ASANA_ACCESS_TOKEN) | Phase 1 |
| Gmail | MCP | Phase 1 |
| Google Calendar | MCP | Phase 1 |
| PinchTab | HTTP localhost:9867 | This session |
| DALL-E | Via OpenAI API | Phase 1 |
