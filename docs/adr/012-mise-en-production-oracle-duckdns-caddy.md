# ADR-012 : Mise en production — Oracle Cloud ARM, DuckDNS, Caddy, images par service et mise à jour mensuelle dans Docker

- **Statut** : Accepté (configuration validée localement ; déploiement sur le serveur à faire par Ahmad, voir [`docs/deploiement.md`](../deploiement.md))
- **Date** : 2026-11-11
- **Décideurs** : Ahmad (hébergeur, nom de domaine) & assistant IA (Claude Code)
- **Exigences liées** : `ENF-01`, `ENF-04`, `ENF-05`, `ENF-06`, `EF-16`, `US-15`, `US-16`
- **Précise** : [`ADR-007`](./007-hebergement-vps-vs-oracle-arm-et-ci-multi-arch.md) (choix tranché), [`ADR-008`](./008-image-unique-et-verrouillage-des-dependances.md) (dette remboursée), [`ADR-011`](./011-detection-anomalies-et-api-publique.md) §5

---

## 1. Décisions

| Sujet | Décision | Alternative écartée |
| :--- | :--- | :--- |
| Hébergeur (Ahmad) | Oracle Cloud « Always Free », VM Ampere ARM 2 OCPU / 12 Go | VPS payant x86 : simple, mais coûte chaque mois |
| Nom de domaine (Ahmad) | Sous-domaine DuckDNS | sslip.io (adresse illisible) ; domaine acheté (payant) |
| Point d'entrée | **Caddy** seul exposé (80/443) : HTTPS Let's Encrypt automatique, redirection HTTP → HTTPS, en-têtes de sécurité | Nginx + certbot : plus de configuration à maintenir |
| Images | Une image par service, chacune construite à partir d'un sous-ensemble du lock | Image unique (dette d'ADR-008) |
| Secrets | Mots de passe lus uniquement dans `.env` ; `docker-compose.prod.yml` refuse de démarrer s'il en manque un | Valeurs par défaut de développement en production |
| Mise à jour mensuelle | Service `scheduler` dans Docker : ETL le 20 de chaque mois à 03:00 UTC, réentraînement **seulement si les données ont changé**, 3 nouvelles tentatives quotidiennes en cas d'échec | Cron de l'hôte (hors Docker) ; GitHub Actions planifié (n'a pas accès à la base du serveur) |

## 2. Images par service (remboursement de la dette d'ADR-008)

`tools/split_lock.py` calcule, pour chaque service, l'ensemble de ses dépendances à partir de leurs métadonnées installées, puis écrit un `requirements/<service>.lock` qui reprend **exactement les versions** de `requirements.lock`. L'image l'installe avec `--no-deps`, et `pip check` garantit que l'ensemble est complet.

| Image | Taille mesurée (`docker images`) | Contenu |
| :--- | ---: | :--- |
| Unique, avant (ADR-008) | 2,05 Go | tout, outils de test compris |
| `agriprix-api` | **459 Mo** | FastAPI, SQLAlchemy, psycopg, slowapi |
| `agriprix-dashboard` | 1,19 Go | Streamlit, Plotly, httpx ; **aucun pilote SQL** |
| `agriprix-mlflow` | 1,46 Go | serveur MLflow |
| `agriprix-jobs` | 1,59 Go | ETL, entraînement, `scheduler` |
| `agriprix-dev` | 2,06 Go | tout ; tests et lint uniquement |

Le critère d'ADR-008 est vérifié : `pip show pytest`, `ruff` et `lightgbm` échouent dans les images de l'API et du dashboard. L'absence de pilote SQL dans l'image du dashboard garantit physiquement la règle EF-13 (le dashboard ne parle qu'à l'API).

La CI construit les 4 images de production pour `linux/arm64` (émulation QEMU) : succès en 5 à 10 minutes par image sur le commit `f529a3f`.

## 3. Sécurité vérifiée (répétition locale du 2026-11-11, `DOMAIN=localhost`)

- Seul Caddy publie des ports (80/443). Les ports 8000, 8501, 5000 et 5432 sont fermés depuis l'hôte.
- HTTP renvoie une redirection 308 vers HTTPS. Les en-têtes `Strict-Transport-Security`, `X-Content-Type-Options`, `X-Frame-Options` et `Referrer-Policy` sont présents, et l'en-tête `Server` est retiré.
- **Limitation de débit derrière le proxy** : la 61ᵉ requête par minute d'un visiteur reçoit un 429, **même s'il envoie une fausse adresse `X-Forwarded-For` différente à chaque requête**. Caddy remplace cet en-tête par l'adresse réelle. Les appels internes du dashboard (réseau Docker, sans en-tête) ne sont pas limités.
- La WebSocket de Streamlit passe par Caddy (`101 Switching Protocols`).
- Script d'initialisation de PostgreSQL : testé sur une base vierge, depuis un autre conteneur. Le mot de passe de `.env` est accepté, même avec une espace et une apostrophe ; un mauvais mot de passe est refusé ; le rôle en lecture seule n'a pas accès à `mlflow_db`.

- Mise à jour mensuelle lancée depuis l'image `agriprix-jobs` : 7 fichiers retéléchargés et vérifiés, 0 observation modifiée, entraînement sauté (comportement attendu). Entraînement forcé : campagne 7 en 4 min 46 s, **36 512 métriques et 2 346 prévisions identiques** à celles de la campagne 6 (image de développement).

## 4. Limites et risques

- **Capacité ARM gratuite** parfois indisponible à la création de la VM (limite connue de l'offre Oracle).
- Deux pare-feu sont à ouvrir côté Oracle (liste de sécurité du VCN **et** `iptables` de la VM), sinon Let's Encrypt échoue.
- **Pas de sauvegarde automatique** de la base : les données sont rechargeables depuis les sources publiques, mais l'historique des campagnes serait perdu (piste : `pg_dump` hebdomadaire).
- Les anciennes campagnes s'accumulent (environ 23 000 alertes et 37 000 métriques par campagne) : une règle de rétention reste à définir.
- La répétition locale utilise un certificat interne de Caddy (non reconnu par les navigateurs). Le certificat Let's Encrypt réel n'a pas encore été obtenu, faute de serveur.
