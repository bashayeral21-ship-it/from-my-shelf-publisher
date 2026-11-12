"""TikTok publisher — Content Posting API (Direct Post). Video and photo posts.

Env: TIKTOK_ACCESS_TOKEN, TIKTOK_REFRESH_TOKEN, TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET
Until TikTok audits the app, posts can only be privacy_level=SELF_ONLY (visible to you only).
After audit, set TIKTOK_PRIVACY=PUBLIC_TO_EVERYONE in the workflow env.
Access tokens last 24h; refresh tokens 365 days — main() refreshes on every run.
"""
import os, time, requests

T = "https://open.tiktokapis.com/v2"


def refresh(client_key, client_secret, refresh_token):
    r = requests.post("https://open.tiktokapis.com/v2/oauth/token/", data={
        "client_key": client_key, "client_secret": client_secret,
        "grant_type": "refresh_token", "refresh_token": refresh_token}, timeout=30).json()
    if "access_token" not in r:
        raise RuntimeError(f"TikTok refresh failed: {r}")
    return r["access_token"], r.get("refresh_token", refresh_token)


def _h(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8"}


def publish_video(token, path, title, privacy="SELF_ONLY"):
    size = os.path.getsize(path)
    chunk = size  # single chunk upload (≤64MB)
    init = requests.post(f"{T}/post/publish/video/init/", headers=_h(token), json={
        "post_info": {"title": title[:2200], "privacy_level": privacy, "disable_duet": False,
                      "disable_comment": False, "disable_stitch": False, "video_cover_timestamp_ms": 1000},
        "source_info": {"source": "FILE_UPLOAD", "video_size": size, "chunk_size": chunk, "total_chunk_count": 1}},
        timeout=30).json()
    if init.get("error", {}).get("code") not in (None, "ok"):
        raise RuntimeError(f"TikTok init failed: {init}")
    d = init["data"]
    with open(path, "rb") as f:
        up = requests.put(d["upload_url"], data=f.read(), headers={
            "Content-Type": "video/mp4", "Content-Range": f"bytes 0-{size-1}/{size}"}, timeout=600)
    if up.status_code not in (200, 201):
        raise RuntimeError(f"TikTok upload failed: {up.status_code} {up.text[:300]}")
    return _wait(token, d["publish_id"])


def publish_photos(token, image_urls, title, description, privacy="SELF_ONLY"):
    r = requests.post(f"{T}/post/publish/content/init/", headers=_h(token), json={
        "post_info": {"title": title[:90], "description": description[:4000], "privacy_level": privacy,
                      "disable_comment": False, "auto_add_music": True},
        "source_info": {"source": "PULL_FROM_URL", "photo_cover_index": 0, "photo_images": image_urls},
        "post_mode": "DIRECT_POST", "media_type": "PHOTO"}, timeout=30).json()
    if r.get("error", {}).get("code") not in (None, "ok"):
        raise RuntimeError(f"TikTok photo init failed: {r}")
    return _wait(token, r["data"]["publish_id"])


def _wait(token, publish_id):
    for _ in range(60):
        s = requests.post(f"{T}/post/publish/status/fetch/", headers=_h(token), json={"publish_id": publish_id}, timeout=30).json()
        st = s.get("data", {}).get("status")
        if st == "PUBLISH_COMPLETE":
            ids = s["data"].get("publicaly_available_post_id") or []
            return f"tiktok:{ids[0]}" if ids else "published"
        if st == "FAILED":
            raise RuntimeError(f"TikTok publish failed: {s}")
        time.sleep(10)
    raise RuntimeError("TikTok publish timed out")
