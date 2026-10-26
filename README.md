# Trend giovani 15-25 anni: dashboard giornaliera gratuita

Fonti: Reddit, YouTube, Google Trends, Twitch. Ogni fonte è facoltativa: si attiva solo se ne
inserisci le credenziali (Google Trends non ne ha bisogno). Senza la chiave Anthropic tutto resta
gratuito: Reddit mostra i post più discussi invece dei temi raggruppati e sintetizzati.

Ogni mattina lo script scarica i post piu discussi delle ultime 24 ore da un panel di subreddit
(Italia, Europa, Mondo), li raggruppa per tema con Claude e aggiorna una dashboard web con i 10 temi
principali per area: volumi, tono prevalente, variazione rispetto al giorno prima, thread di esempio,
storico dei giorni precedenti. Se configuri i dati SMTP arriva anche la mail.

## Configurazione (circa 20 minuti, una volta sola)

1. **Repository GitHub privato.** Crea un repository privato e carica tutti i file di questa cartella,
   inclusa `.github/workflows/`.
2. **App Reddit.** Da un account Reddit vai su https://www.reddit.com/prefs/apps, "create app",
   tipo "script". Annota client ID (sotto il nome dell'app) e secret. Reddit puo chiedere di
   registrare l'uso dell'API e di accettare i termini per sviluppatori; l'uso commerciale richiede
   un accordo specifico con Reddit.
3. **Chiave API Anthropic.** Da https://console.anthropic.com, sezione API Keys.
4. **Email di invio (facoltativa).** Se lasci vuoti i secret SMTP la mail non parte e si aggiorna solo la dashboard. Con Gmail o Google Workspace: attiva la verifica in due passaggi e genera una
   "password per le app" dalle impostazioni di sicurezza dell'account Google.
5. **YouTube (facoltativo, gratuito).** Su https://console.cloud.google.com crea un progetto, abilita
   "YouTube Data API v3" e genera una chiave API. La quota gratuita basta ampiamente.
   **Twitch (facoltativo, gratuito).** Su https://dev.twitch.tv/console registra un'applicazione
   (URL di reindirizzamento: `http://localhost`) e annota client ID e secret.
6. **Secrets.** Nel repository: Settings > Secrets and variables > Actions > New repository secret.

| Secret | Valore |
|---|---|
| REDDIT_CLIENT_ID | client ID dell'app Reddit |
| REDDIT_CLIENT_SECRET | secret dell'app Reddit |
| REDDIT_USERNAME | nome utente Reddit (per lo user agent) |
| ANTHROPIC_API_KEY | chiave API Anthropic |
| SMTP_HOST | smtp.gmail.com |
| SMTP_PORT | 465 |
| SMTP_USER | indirizzo che invia |
| SMTP_PASSWORD | password per le app |
| MAIL_TO | destinatari, separati da virgola |
| YOUTUBE_API_KEY | chiave YouTube Data API v3 |
| TWITCH_CLIENT_ID | client ID dell'app Twitch |
| TWITCH_CLIENT_SECRET | secret dell'app Twitch |

7. **Dashboard.** Settings > Pages > Source: "Deploy from a branch", branch `main`, cartella `/docs`.
   L'indirizzo sarà `https://<utente>.github.io/<repository>/`. Con un account GitHub gratuito Pages
   funziona solo su repository pubblici; per un repository privato serve GitHub Pro (4 $/mese).
   I dati sono trend pubblici di Reddit, ma l'indirizzo della dashboard sarà raggiungibile da chiunque lo conosca.
8. **Test.** Scheda Actions > "Trend giovani giornaliero" > Run workflow. Dopo 2-3 minuti la dashboard
   mostra il primo giorno (Pages può impiegare un altro minuto a pubblicare).

## Personalizzazione

- Subreddit monitorati e numero di temi: `config.json`.
- Orario: riga `cron` nel workflow (orario UTC). GitHub puo ritardare l'avvio di 10-30 minuti.
- Lo storico giornaliero viene salvato in `docs/data/` e serve per calcolare le variazioni.

## Costi

Con repository pubblico tutto è gratuito: GitHub Actions, GitHub Pages, API di Reddit, YouTube, Twitch
e il feed di Google Trends. L'unica voce facoltativa a pagamento è l'API Anthropic per raggruppare e
sintetizzare i temi Reddit (pochi centesimi al giorno).

## Fonti escluse dall'automazione

- **TikTok Creative Center**: non ha un'API pubblica e i termini d'uso vietano la raccolta automatica.
  Va consultato a mano (ads.tiktok.com/business/creativecenter), filtro Paese Italia.
- **Spotify Viral 50**: dal 2024 le API di Spotify non danno più accesso alle playlist editoriali
  alle nuove applicazioni.
- **Telegram**: si possono aggiungere canali pubblici, ma serve prima un elenco dei canali da seguire.

## Limiti

Reddit non espone l'eta degli utenti: la fascia 15-25 e approssimata tramite la scelta dei subreddit.
In Italia la piattaforma e piu rappresentativa dei 19-25enni che dei minorenni.
