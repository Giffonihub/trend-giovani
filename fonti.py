"""Fonti aggiuntive al monitoraggio: YouTube, Google Trends, Twitch.
Ogni fonte si attiva solo se le sue credenziali sono presenti; se fallisce, viene saltata."""

import os
import xml.etree.ElementTree as ET

import requests

PAESI = {"Italia": ["IT"], "Europa": ["DE", "FR", "ES", "GB"], "Mondo": ["US", "BR", "IN"]}
LINGUE_TWITCH = {"Italia": ["it"], "Europa": ["de", "fr", "es"], "Mondo": [None]}


def _avviso(fonte, e):
    print(f"[avviso] {fonte}: {e}")


# ---------- YouTube (API gratuita, chiave da Google Cloud) ----------

def youtube(area):
    key = os.environ.get("YOUTUBE_API_KEY")
    if not key:
        return None
    video = []
    for paese in PAESI[area]:
        try:
            r = requests.get("https://www.googleapis.com/youtube/v3/videos", timeout=30, params={
                "part": "snippet,statistics", "chart": "mostPopular", "regionCode": paese,
                "maxResults": 20, "key": key})
            r.raise_for_status()
            for v in r.json().get("items", []):
                s, st = v["snippet"], v.get("statistics", {})
                video.append({
                    "titolo": s.get("title", ""), "canale": s.get("channelTitle", ""), "paese": paese,
                    "visualizzazioni": int(st.get("viewCount", 0)), "commenti": int(st.get("commentCount", 0)),
                    "url": f"https://www.youtube.com/watch?v={v['id']}"})
        except Exception as e:
            _avviso(f"YouTube {paese}", e)
    video.sort(key=lambda v: v["commenti"], reverse=True)
    return video[:10] or None


# ---------- Google Trends (feed RSS pubblico, nessuna chiave) ----------

def _figlio(nodo, nome):
    for c in nodo:
        if c.tag.split("}")[-1] == nome:
            return c
    return None


def google_trends(area):
    ricerche = []
    for paese in PAESI[area]:
        try:
            r = requests.get("https://trends.google.com/trending/rss", params={"geo": paese}, timeout=30,
                             headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            for item in ET.fromstring(r.content).iter("item"):
                traffico = _figlio(item, "approx_traffic")
                notizia = _figlio(item, "news_item")
                titolo_n = _figlio(notizia, "news_item_title") if notizia is not None else None
                url_n = _figlio(notizia, "news_item_url") if notizia is not None else None
                t = (traffico.text if traffico is not None else "0").replace("+", "").replace(",", "").replace(".", "")
                ricerche.append({
                    "ricerca": _figlio(item, "title").text, "paese": paese,
                    "volume": int(t) if t.isdigit() else 0, "volume_testo": traffico.text if traffico is not None else "",
                    "notizia": titolo_n.text if titolo_n is not None else "",
                    "url": url_n.text if url_n is not None else ""})
        except Exception as e:
            _avviso(f"Google Trends {paese}", e)
    ricerche.sort(key=lambda x: x["volume"], reverse=True)
    return ricerche[:15] or None


# ---------- Twitch (API gratuita, app su dev.twitch.tv) ----------

_twitch_token = None


def _twitch_headers():
    global _twitch_token
    cid, sec = os.environ.get("TWITCH_CLIENT_ID"), os.environ.get("TWITCH_CLIENT_SECRET")
    if not (cid and sec):
        return None
    if not _twitch_token:
        r = requests.post("https://id.twitch.tv/oauth2/token", timeout=30, data={
            "client_id": cid, "client_secret": sec, "grant_type": "client_credentials"})
        r.raise_for_status()
        _twitch_token = r.json()["access_token"]
    return {"Client-Id": cid, "Authorization": f"Bearer {_twitch_token}"}


def twitch(area):
    try:
        h = _twitch_headers()
    except Exception as e:
        _avviso("Twitch login", e)
        return None
    if not h:
        return None
    categorie, streamer = {}, []
    for lingua in LINGUE_TWITCH[area]:
        try:
            params = {"first": 100}
            if lingua:
                params["language"] = lingua
            r = requests.get("https://api.twitch.tv/helix/streams", headers=h, params=params, timeout=30)
            r.raise_for_status()
            for s in r.json().get("data", []):
                g = s.get("game_name") or "Altro"
                categorie[g] = categorie.get(g, 0) + s.get("viewer_count", 0)
                streamer.append({"nome": s.get("user_name", ""), "categoria": g,
                                 "spettatori": s.get("viewer_count", 0),
                                 "url": f"https://www.twitch.tv/{s.get('user_login', '')}"})
        except Exception as e:
            _avviso(f"Twitch {lingua}", e)
    if not categorie:
        return None
    top_cat = sorted(({"categoria": k, "spettatori": v} for k, v in categorie.items()),
                     key=lambda x: x["spettatori"], reverse=True)[:10]
    streamer.sort(key=lambda x: x["spettatori"], reverse=True)
    return {"categorie": top_cat, "streamer": streamer[:5]}


def raccogli(area):
    out = {}
    for nome, f in (("youtube", youtube), ("google_trends", google_trends), ("twitch", twitch)):
        dati = f(area)
        if dati:
            out[nome] = dati
    return out
