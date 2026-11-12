"""Instagram publisher — Meta Graph API content publishing (Reels, images, carousels, Stories).

Env: IG_ACCESS_TOKEN (long-lived user/page token), IG_USER_ID (Instagram Business account id),
     META_APP_ID, META_APP_SECRET (only for token refresh).
Media must be reachable by Meta over a public URL; the workflow publishes repo media through
GitHub raw URLs (public repo) or a release asset. Pass media_url, not a local path.
"""
import time, requests

G = "https://graph.facebook.com/v21.0"


def _wait_container(token, cid):
    for _ in range(90):  # up to ~15 min
        r = requests.get(f"{G}/{cid}", params={"fields": "status_code,status", "access_token": token}, timeout=30).json()
        if r.get("status_code") == "FINISHED":
            return
        if r.get("status_code") == "ERROR":
            raise RuntimeError(f"IG container error: {r}")
        time.sleep(10)
    raise RuntimeError("IG container still processing after 15 min")


def _create(token, ig_user, **params):
    params["access_token"] = token
    r = requests.post(f"{G}/{ig_user}/media", data=params, timeout=60).json()
    if "id" not in r:
        raise RuntimeError(f"IG create failed: {r}")
    return r["id"]


def _publish(token, ig_user, cid):
    for attempt in range(6):
        r = requests.post(f"{G}/{ig_user}/media_publish", data={"creation_id": cid, "access_token": token}, timeout=60).json()
        if "id" in r:
            return r["id"]
        msg = str(r)
        if "processing" in msg.lower() or "9007" in msg:
            time.sleep(30); continue
        raise RuntimeError(f"IG publish failed: {r}")
    raise RuntimeError("IG publish: media still processing after retries")


def publish(token, ig_user, caption, media_urls, kind="reel"):
    """kind: reel | image | carousel | story_image | story_video"""
    if kind == "reel":
        cid = _create(token, ig_user, media_type="REELS", video_url=media_urls[0], caption=caption, share_to_feed="true")
    elif kind == "image":
        cid = _create(token, ig_user, image_url=media_urls[0], caption=caption)
    elif kind == "carousel":
        children = []
        for u in media_urls:
            p = {"is_carousel_item": "true"}
            if u.lower().endswith((".mp4", ".mov")):
                p.update(media_type="VIDEO", video_url=u)
            else:
                p["image_url"] = u
            children.append(_create(token, ig_user, **p))
        for c in children:
            _wait_container(token, c)
        cid = _create(token, ig_user, media_type="CAROUSEL", children=",".join(children), caption=caption)
    elif kind == "story_image":
        cid = _create(token, ig_user, media_type="STORIES", image_url=media_urls[0])
    elif kind == "story_video":
        cid = _create(token, ig_user, media_type="STORIES", video_url=media_urls[0])
    else:
        raise ValueError(kind)
    _wait_container(token, cid)
    mid = _publish(token, ig_user, cid)
    r = requests.get(f"{G}/{mid}", params={"fields": "permalink", "access_token": token}, timeout=30).json()
    return r.get("permalink", mid)


def refresh_long_lived(token, app_id, app_secret):
    r = requests.get(f"{G}/oauth/access_token", params={"grant_type": "fb_exchange_token", "client_id": app_id,
                                                        "client_secret": app_secret, "fb_exchange_token": token}, timeout=30).json()
    return r.get("access_token")


def token_expiry_days(token, app_id, app_secret):
    r = requests.get(f"{G}/debug_token", params={"input_token": token, "access_token": f"{app_id}|{app_secret}"}, timeout=30).json()
    exp = r.get("data", {}).get("expires_at", 0)
    return (exp - time.time()) / 86400 if exp else 999
