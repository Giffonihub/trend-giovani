"""Report giornaliero dei temi piu discussi su Reddit tra i 15-25enni.
Raccoglie i post top delle ultime 24 ore da un panel di subreddit,
li raggruppa per tema con Claude e invia il report via email."""

import datetime as dt
import html
import json
import os
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import requests

import fonti

UA = "python:gih-trend-reddit:v1.0 (by /u/" + os.environ.get("REDDIT_USERNAME", "gih_trend") + ")"
MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5")
CONFIG = json.loads(Path("config.json").read_text(encoding="utf-8"))
DATA = Path("docs/data")
DATA.mkdir(parents=True, exist_ok=True)
OGGI = dt.date.today().isoformat()


# ---------- Reddit ----------

def reddit_token():
    r = requests.post(
        "https://www.reddit.com/api/v1/access_token",
        auth=(os.environ["REDDIT_CLIENT_ID"], os.environ["REDDIT_CLIENT_SECRET"]),
        data={"grant_type": "client_credentials"},
        headers={"User-Agent": UA},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def scarica_subreddit(sub, token, limit):
    r = requests.get(
        f"https://oauth.reddit.com/r/{sub}/top",
        headers={"Authorization": f"bearer {token}", "User-Agent": UA},
        params={"t": "day", "limit": limit},
        timeout=30,
    )
    time.sleep(1)  # rispetto dei limiti di frequenza
    if r.status_code != 200:
        print(f"[avviso] r/{sub}: HTTP {r.status_code}, saltato")
        return []
    post = []
    for c in r.json().get("data", {}).get("children", []):
        d = c["data"]
        if d.get("stickied") or d.get("over_18"):
            continue
        post.append({
            "sub": sub,
            "titolo": d.get("title", ""),
            "testo": (d.get("selftext") or "")[:250].replace("\n", " "),
            "upvote": d.get("score", 0),
            "commenti": d.get("num_comments", 0),
            "url": "https://www.reddit.com" + d.get("permalink", ""),
        })
    return post


def engagement(p):
    return p["upvote"] + 2 * p["commenti"]


# ---------- Claude ----------

def chiama_claude(prompt):
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={"model": MODEL, "max_tokens": 4000,
              "messages": [{"role": "user", "content": prompt}]},
        timeout=180,
    )
    r.raise_for_status()
    testo = "".join(b.get("text", "") for b in r.json()["content"])
    testo = testo.replace("```json", "").replace("```", "").strip()
    return json.loads(testo[testo.find("{"): testo.rfind("}") + 1])


def analizza_area(area, post, temi_ieri, n_temi):
    righe = [
        f"[{i}] r/{p['sub']} | {p['upvote']} upvote | {p['commenti']} commenti | {p['titolo']} | {p['testo']}"
        for i, p in enumerate(post)
    ]
    ieri = "\n".join(f"- {t['titolo']} (engagement {t['engagement']})" for t in temi_ieri) or "nessun dato"
    prompt = f"""Analizzi le conversazioni su Reddit di ragazzi e giovani adulti (15-25 anni), area: {area}.
Qui sotto i post piu votati delle ultime 24 ore, numerati.

{chr(10).join(righe)}

Temi principali di ieri per quest'area:
{ieri}

Compito:
1. Raggruppa i post in temi di conversazione (non per subreddit). Ignora meme isolati senza discussione.
2. Restituisci i {n_temi} temi piu rilevanti per volume di discussione.
3. Per ogni tema: titolo breve in italiano, sintesi in 1-2 frasi in italiano (cosa si discute e con quale posizione prevalente), indici dei post che ne fanno parte, tono prevalente, variazione rispetto a ieri.

Rispondi SOLO con JSON valido, senza testo prima o dopo, in questo formato:
{{"temi": [{{"titolo": "...", "sintesi": "...", "post": [0, 5, 12], "tono": "positivo|negativo|misto|neutro", "variazione": "nuovo|in crescita|stabile|in calo"}}]}}"""
    return chiama_claude(prompt)["temi"]


# ---------- Storico ----------

def storico_precedente():
    file = sorted(f for f in DATA.glob("20*.json") if f.stem < OGGI)
    if not file:
        return {}
    prec = json.loads(file[-1].read_text(encoding="utf-8"))
    return {a: v["temi"] for a, v in prec.get("aree", {}).items()}


def salva_giorno(risultati, totali, altre):
    giorno = {"data": OGGI, "generato": dt.datetime.now(dt.timezone.utc).isoformat(), "aree": {}}
    for area, temi in risultati.items():
        giorno["aree"][area] = {**totali[area], "temi": [
            {k: t[k] for k in ("titolo", "sintesi", "tono", "variazione", "n_post", "commenti", "engagement")}
            | {"esempi": [{"sub": p["sub"], "titolo": p["titolo"], "url": p["url"]} for p in t["esempi"]]}
            for t in temi]}
    for area, f in altre.items():
        giorno["aree"].setdefault(area, {"temi": []})["fonti"] = f
    (DATA / f"{OGGI}.json").write_text(json.dumps(giorno, ensure_ascii=False, indent=1), encoding="utf-8")
    indice_f = DATA / "index.json"
    indice = json.loads(indice_f.read_text(encoding="utf-8")) if indice_f.exists() else []
    indice = [g for g in indice if g["data"] != OGGI]
    indice.append({"data": OGGI, "aree": {a: totali.get(a, {}) for a in CONFIG["aree"]}})
    indice.sort(key=lambda g: g["data"])
    indice_f.write_text(json.dumps(indice, ensure_ascii=False, indent=1), encoding="utf-8")


# ---------- Email ----------

COLORI_TONO = {"positivo": "#2e7d32", "negativo": "#c62828", "misto": "#ef6c00", "neutro": "#616161"}


def html_report(risultati):
    parti = [f"<h2 style='margin:0 0 4px'>Trend Reddit 15-25 anni</h2>"
             f"<p style='color:#666;margin:0 0 20px'>{dt.date.today().strftime('%d/%m/%Y')}, ultime 24 ore</p>"]
    for area, temi in risultati.items():
        parti.append(f"<h3 style='border-bottom:2px solid #222;padding-bottom:4px'>{area}</h3><ol>")
        for t in temi:
            link = " ".join(
                f"<a href='{html.escape(p['url'])}'>r/{html.escape(p['sub'])}</a>" for p in t["esempi"]
            )
            colore = COLORI_TONO.get(t["tono"], "#616161")
            parti.append(
                f"<li style='margin-bottom:14px'><b>{html.escape(t['titolo'])}</b> "
                f"<span style='color:#666'>({t['n_post']} post, {t['commenti']} commenti, {t['variazione']})</span><br>"
                f"{html.escape(t['sintesi'])}<br>"
                f"<span style='color:{colore}'>Tono: {t['tono']}</span> &middot; {link}</li>"
            )
        parti.append("</ol>")
    parti.append("<p style='color:#999;font-size:12px'>Fonte: panel di subreddit a pubblico giovane. "
                 "Reddit non espone l'eta degli utenti: la fascia 15-25 e un'approssimazione.</p>")
    return "<div style='font-family:Arial,sans-serif;max-width:680px'>" + "".join(parti) + "</div>"


def invia_email(corpo_html):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Trend Reddit 15-25, {dt.date.today().strftime('%d/%m/%Y')}"
    msg["From"] = os.environ["SMTP_USER"]
    destinatari = [d.strip() for d in os.environ["MAIL_TO"].split(",")]
    msg["To"] = ", ".join(destinatari)
    msg.attach(MIMEText(corpo_html, "html", "utf-8"))
    with smtplib.SMTP_SSL(os.environ.get("SMTP_HOST", "smtp.gmail.com"),
                          int(os.environ.get("SMTP_PORT", "465"))) as s:
        s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
        s.sendmail(msg["From"], destinatari, msg.as_string())


# ---------- Main ----------

def temi_senza_ai(post, n):
    """Alternativa gratuita se manca la chiave Anthropic: i post piu discussi, senza raggruppamento."""
    return [{"titolo": p["titolo"], "sintesi": f"Post su r/{p['sub']}", "tono": "n.d.",
             "variazione": "n.d.", "post": [i]} for i, p in enumerate(post[:n])]


def main():
    risultati, totali, altre = {}, {}, {}
    ieri = storico_precedente()
    try:
        token = reddit_token() if os.environ.get("REDDIT_CLIENT_ID") else None
    except Exception as e:
        print(f"[avviso] Reddit login: {e}")
        token = None

    for area, subs in CONFIG["aree"].items():
        altre[area] = fonti.raccogli(area)
        if not token:
            continue
        post = []
        for sub in subs:
            post += scarica_subreddit(sub, token, CONFIG["post_per_subreddit"])
        post = sorted(post, key=engagement, reverse=True)[: CONFIG["post_max_per_area"]]
        if not post:
            continue
        if os.environ.get("ANTHROPIC_API_KEY"):
            try:
                temi = analizza_area(area, post, ieri.get(area, []), CONFIG["temi_per_area"])
            except Exception as e:
                print(f"[avviso] Claude {area}: {e}")
                temi = temi_senza_ai(post, CONFIG["temi_per_area"])
        else:
            temi = temi_senza_ai(post, CONFIG["temi_per_area"])

        for t in temi:
            membri = [post[i] for i in t.get("post", []) if isinstance(i, int) and 0 <= i < len(post)]
            t["n_post"] = len(membri)
            t["commenti"] = sum(p["commenti"] for p in membri)
            t["engagement"] = sum(engagement(p) for p in membri)
            t["esempi"] = sorted(membri, key=engagement, reverse=True)[:3]
        temi.sort(key=lambda t: t["engagement"], reverse=True)

        risultati[area] = temi
        totali[area] = {"post_analizzati": len(post), "commenti_totali": sum(p["commenti"] for p in post)}

    salva_giorno(risultati, totali, altre)
    print("Dashboard aggiornata.")
    if os.environ.get("SMTP_USER") and risultati:
        invia_email(html_report(risultati))
        print("Email inviata.")


if __name__ == "__main__":
    main()
