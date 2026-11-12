# من رفّي — social publisher (free, self-hosted on GitHub Actions)

Posts to **Instagram, LinkedIn and TikTok** from one `schedule.csv`, every day at **19:47 Asia/Dubai**
(or on demand from the Actions tab → *Publish scheduled posts* → *Run workflow*). No Metricool, no Zapier.

## How to add a post
1. Drop the media into `media/` (video ≤ 100 MB for GitHub; name it like `NN-ar-reel.mp4`).
2. Put the caption in `captions/<name>.txt`. Platform-specific caption: `captions/<name>.txt.linkedin.txt`.
3. Add a row to `schedule.csv`:

| column | example | notes |
|---|---|---|
| date | 2026-11-10 | Asia/Dubai |
| time | 19:47 | optional, default 19:47 |
| platforms | instagram,tiktok | any of instagram, linkedin, tiktok |
| type | reel | reel · image · carousel · story_image · story_video · video · text |
| media | media/02-ar-reel.mp4 | carousel: comma-separated images |
| caption_file | captions/02-ar.txt | |
| title | (TikTok title) | optional |
| status | pending | the bot writes published / partial / failed |
| result | | post URLs written by the bot |

Commit → done. The bot updates the row with the result and sends a notification (optional webhook).

## One-time setup (secrets → repo Settings → Secrets and variables → Actions)

### LinkedIn (works immediately)
1. https://www.linkedin.com/developers/apps → **Create app** (attach any LinkedIn Page you admin).
2. **Products** → add *Share on LinkedIn* and *Sign In with LinkedIn using OpenID Connect*.
3. **Auth** tab → *OAuth 2.0 tools* → *Create token* → scopes `openid profile w_member_social` → sign in → copy the access token.
4. Secret `LINKEDIN_ACCESS_TOKEN` = that token. **Expires every 60 days** — the bot's run log says "LinkedIn token INVALID" when it's time; repeat step 3.

### Instagram (Business account linked to a Facebook Page)
1. https://developers.facebook.com/apps → **Create app** → type *Business* → add product **Instagram** (Instagram API with Facebook Login).
2. Settings → Basic: copy **App ID** → secret `META_APP_ID`; **App Secret** → secret `META_APP_SECRET`.
3. Tools → **Graph API Explorer**: pick your app, add permissions `instagram_basic, instagram_content_publish, pages_show_list, pages_read_engagement, business_management` → *Generate Access Token* → log in.
4. In the Explorer run `GET me/accounts?fields=instagram_business_account` → copy the `instagram_business_account.id` → secret `IG_USER_ID`.
5. Turn the token into a long-lived one (60 days, auto-refreshed by the bot): open in a browser
   `https://graph.facebook.com/v21.0/oauth/access_token?grant_type=fb_exchange_token&client_id=APP_ID&client_secret=APP_SECRET&fb_exchange_token=SHORT_TOKEN`
   → secret `IG_ACCESS_TOKEN`.
6. For auto-refresh to write the new token back, add secret `ADMIN_PAT` = a fine-grained GitHub PAT with *Secrets: read & write* on this repo. Without it the bot still warns you 10 days before expiry.
7. Repo must be **public** (Meta fetches media by URL) — or set repo variable `MEDIA_PUBLIC_BASE` to another public base URL.

### TikTok (needs app audit before public posts)
1. https://developers.tiktok.com → **Manage apps** → create app → add **Content Posting API** + **Login Kit**; scopes `video.publish, video.upload, user.info.basic`.
2. Secrets `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET`.
3. Authorize once (Login Kit URL with `redirect_uri` set to the repo's GitHub Pages URL or any URL you own) → exchange the code for tokens → secret `TIKTOK_REFRESH_TOKEN` (refresh tokens last 365 days; the bot refreshes the access token on every run).
4. Until TikTok approves the audit, posts are **private to you** (`SELF_ONLY`). After approval set repo variable `TIKTOK_PRIVACY = PUBLIC_TO_EVERYONE`.

## Notifications
Optional secret `NOTIFY_WEBHOOK` (Slack incoming webhook, Discord webhook, or a Zapier catch-hook that forwards to WhatsApp/SMS). The run log in the Actions tab always has the full report.

## Limits that are real
- Instagram: 25 API posts / 24 h. LinkedIn: no practical limit. TikTok: audited apps are unlimited.
- GitHub Actions free tier: 2,000 minutes/month; a run takes ~1–3 minutes.
- GitHub file size: ≤ 100 MB per file; keep reels under ~50 MB.
