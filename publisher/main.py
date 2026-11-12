"""Social publisher — runs on GitHub Actions at 19:47 Asia/Dubai (and on manual dispatch).

Reads schedule.csv, publishes every row whose date/time is due (≤ now, Asia/Dubai) and status is
'pending', writes status/result back, and commits the file. One row can target several platforms
(instagram,linkedin,tiktok); a per-platform caption file overrides caption_file when named
<caption_file>.<platform>.txt (e.g. captions/x.txt.linkedin.txt).

schedule.csv columns:
  date,time,platforms,type,media,caption_file,title,status,result
  type: reel | image | carousel | story_image | story_video | video | text
  media: comma-separated repo paths (carousel: slide_01.jpg,slide_02.jpg,...)
"""
import csv, os, sys, datetime as dt, zoneinfo, traceback
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent.parent
TZ = zoneinfo.ZoneInfo("Asia/Dubai")
SCHEDULE = ROOT / "schedule.csv"
REPO = os.environ.get("GITHUB_REPOSITORY", "")
BRANCH = os.environ.get("GITHUB_REF_NAME", "main")
PUBLIC_BASE = os.environ.get("MEDIA_PUBLIC_BASE") or (f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/" if REPO else "")


def public_url(path):
    if not PUBLIC_BASE:
        raise RuntimeError("MEDIA_PUBLIC_BASE not set and not running in GitHub")
    return PUBLIC_BASE + requests.utils.quote(path)


def read_caption(base, platform):
    p = ROOT / f"{base}.{platform}.txt"
    if not p.exists():
        p = ROOT / base
    return p.read_text(encoding="utf-8").strip() if p.exists() else ""


def notify(msg):
    print(msg)
    hook = os.environ.get("NOTIFY_WEBHOOK")  # optional: Slack/Discord/Zapier catch hook
    if hook:
        try:
            requests.post(hook, json={"text": msg, "content": msg}, timeout=15)
        except Exception:
            pass


def due(row, now):
    try:
        when = dt.datetime.strptime(f"{row['date']} {row['time'] or '19:47'}", "%Y-%m-%d %H:%M").replace(tzinfo=TZ)
    except ValueError:
        return False
    return row.get("status", "pending") in ("", "pending") and when <= now


def publish_row(row):
    from publisher import linkedin, instagram, tiktok
    media = [m.strip() for m in (row.get("media") or "").split(",") if m.strip()]
    kind = (row.get("type") or "text").strip()
    title = row.get("title") or ""
    results, errors = [], []
    for platform in [p.strip().lower() for p in row["platforms"].split(",") if p.strip()]:
        caption = read_caption(row.get("caption_file", ""), platform)
        try:
            if platform == "linkedin":
                tok = os.environ["LINKEDIN_ACCESS_TOKEN"]
                k = "video" if kind in ("reel", "video", "story_video") else ("image" if kind in ("image", "carousel", "story_image") else "text")
                path = str(ROOT / media[0]) if media else None
                results.append(f"linkedin={linkedin.publish(tok, caption, path, k, title)}")
            elif platform == "instagram":
                tok, ig = os.environ["IG_ACCESS_TOKEN"], os.environ["IG_USER_ID"]
                k = {"video": "reel"}.get(kind, kind)
                results.append(f"instagram={instagram.publish(tok, ig, caption, [public_url(m) for m in media], k)}")
            elif platform == "tiktok":
                ck, cs = os.environ["TIKTOK_CLIENT_KEY"], os.environ["TIKTOK_CLIENT_SECRET"]
                tok, _ = tiktok.refresh(ck, cs, os.environ["TIKTOK_REFRESH_TOKEN"])
                priv = os.environ.get("TIKTOK_PRIVACY", "SELF_ONLY")
                if kind in ("reel", "video"):
                    results.append(f"tiktok={tiktok.publish_video(tok, str(ROOT / media[0]), title or caption.split(chr(10))[0], priv)}")
                else:
                    results.append(f"tiktok={tiktok.publish_photos(tok, [public_url(m) for m in media], title or caption.split(chr(10))[0], caption, priv)}")
            else:
                errors.append(f"{platform}=unknown platform")
        except Exception as e:  # keep going with the other platforms
            errors.append(f"{platform}=ERROR {str(e)[:300]}")
            traceback.print_exc()
    return results, errors


def check_tokens():
    """Warn early about expiring tokens; refresh IG automatically when possible."""
    from publisher import instagram
    notes = []
    tok = os.environ.get("IG_ACCESS_TOKEN"); app, sec = os.environ.get("META_APP_ID"), os.environ.get("META_APP_SECRET")
    if tok and app and sec:
        try:
            days = instagram.token_expiry_days(tok, app, sec)
            if days < 10:
                new = instagram.refresh_long_lived(tok, app, sec)
                if new:
                    Path(ROOT / ".new_ig_token").write_text(new)
                    notes.append("IG token refreshed — workflow will store it as a secret")
            notes.append(f"IG token expires in {days:.0f} days")
        except Exception as e:
            notes.append(f"IG token check failed: {e}")
    li = os.environ.get("LINKEDIN_ACCESS_TOKEN")
    if li:
        r = requests.get("https://api.linkedin.com/v2/userinfo", headers={"Authorization": f"Bearer {li}"}, timeout=30)
        notes.append("LinkedIn token OK" if r.ok else f"LinkedIn token INVALID ({r.status_code}) — re-authorize at https://www.linkedin.com/developers/tools/oauth")
    return notes


def main():
    now = dt.datetime.now(TZ)
    rows = list(csv.DictReader(SCHEDULE.open(encoding="utf-8")))
    fields = rows[0].keys() if rows else ["date", "time", "platforms", "type", "media", "caption_file", "title", "status", "result"]
    report = [f"Run {now:%Y-%m-%d %H:%M} Asia/Dubai"] + check_tokens()
    changed = False
    for row in rows:
        if not due(row, now):
            continue
        ok, bad = publish_row(row)
        row["status"] = "published" if ok and not bad else ("partial" if ok else "failed")
        row["result"] = " | ".join(ok + bad)
        report.append(f"{row['date']} {row['platforms']} → {row['status']}: {row['result']}")
        changed = True
    if changed:
        with SCHEDULE.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)
    notify("\n".join(report))
    if any("failed" in r for r in report):
        sys.exit(1)


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    main()
