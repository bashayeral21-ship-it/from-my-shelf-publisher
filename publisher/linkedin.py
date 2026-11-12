"""LinkedIn publisher — Posts API (text / image / native video) on the member's own profile.

Env: LINKEDIN_ACCESS_TOKEN (scope: w_member_social, openid, profile)
Token lifetime: 60 days. publisher.main checks /userinfo and fails loudly when expired.
"""
import os, time, requests

API = "https://api.linkedin.com"
VERSION = "202410"


def _h(token, json=True):
    h = {"Authorization": f"Bearer {token}", "LinkedIn-Version": VERSION, "X-Restli-Protocol-Version": "2.0.0"}
    if json:
        h["Content-Type"] = "application/json"
    return h


def person_urn(token):
    r = requests.get(f"{API}/v2/userinfo", headers=_h(token, False), timeout=30)
    r.raise_for_status()
    return f"urn:li:person:{r.json()['sub']}"


def _upload_image(token, owner, path):
    r = requests.post(f"{API}/rest/images?action=initializeUpload", headers=_h(token),
                      json={"initializeUploadRequest": {"owner": owner}}, timeout=30)
    r.raise_for_status()
    v = r.json()["value"]
    with open(path, "rb") as f:
        up = requests.put(v["uploadUrl"], data=f, headers={"Authorization": f"Bearer {token}"}, timeout=300)
    up.raise_for_status()
    return v["image"]


def _upload_video(token, owner, path):
    size = os.path.getsize(path)
    r = requests.post(f"{API}/rest/videos?action=initializeUpload", headers=_h(token),
                      json={"initializeUploadRequest": {"owner": owner, "fileSizeBytes": size,
                                                        "uploadCaptions": False, "uploadThumbnail": False}}, timeout=30)
    r.raise_for_status()
    v = r.json()["value"]
    etags = []
    with open(path, "rb") as f:
        for inst in v["uploadInstructions"]:
            first, last = inst["firstByte"], inst["lastByte"]
            f.seek(first)
            chunk = f.read(last - first + 1)
            up = requests.put(inst["uploadUrl"], data=chunk,
                              headers={"Content-Type": "application/octet-stream"}, timeout=600)
            up.raise_for_status()
            etags.append(up.headers["ETag"])
    fin = requests.post(f"{API}/rest/videos?action=finalizeUpload", headers=_h(token),
                        json={"finalizeUploadRequest": {"video": v["video"], "uploadToken": v.get("uploadToken", ""),
                                                        "uploadedPartIds": etags}}, timeout=30)
    fin.raise_for_status()
    # wait until processed
    for _ in range(60):
        s = requests.get(f"{API}/rest/videos/{requests.utils.quote(v['video'], safe='')}", headers=_h(token, False), timeout=30)
        if s.ok and s.json().get("status") == "AVAILABLE":
            break
        time.sleep(10)
    return v["video"]


def publish(token, text, media_path=None, kind="text", title=None):
    owner = person_urn(token)
    body = {"author": owner, "commentary": text, "visibility": "PUBLIC",
            "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [], "thirdPartyDistributionChannels": []},
            "lifecycleState": "PUBLISHED", "isReshareDisabledByAuthor": False}
    if kind == "image" and media_path:
        body["content"] = {"media": {"id": _upload_image(token, owner, media_path), "title": title or ""}}
    elif kind == "video" and media_path:
        body["content"] = {"media": {"id": _upload_video(token, owner, media_path), "title": title or ""}}
    r = requests.post(f"{API}/rest/posts", headers=_h(token), json=body, timeout=60)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"LinkedIn {r.status_code}: {r.text[:400]}")
    post_id = r.headers.get("x-restli-id", "")
    return f"https://www.linkedin.com/feed/update/{post_id}" if post_id else "published"
