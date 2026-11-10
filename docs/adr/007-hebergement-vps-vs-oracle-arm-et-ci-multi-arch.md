# ADR-007 : Stratégie d'hébergement de la démo publique (VPS x86 low-cost vs VM ARM Oracle Cloud) et CI Multi-Architecture (`amd64` + `arm64`)

- **Statut** : Accepté
- **Date** : 2026-11-03
- **Décideurs** : Amine & Ingénieur Data/Logiciel Junior
- **Exigences liées** : `SMART-06`, `EF-18`, `ENF-07`, `ENF-08`, `US-02`, `US-16`, `US-17`

---

## 1. Contexte et Problème

Pour maximiser l'impact du portfolio d'Amine auprès des recruteurs (Data Science / Data Engineering / MIAGE), AgriPrix Observatory doit disposer :
1. D'une **démo publique accessible en HTTPS** (permettant au recruteur de tester le dashboard Streamlit et la documentation Swagger de l'API en un clic depuis le CV ou le `README.md`, sans cloner le dépôt).
2. D'une **reproductibilité locale totale en une commande (`docker compose up`)** au cas où le serveur cloud serait mis en veille après la campagne de recherche de stage.

En tant qu'étudiant, Amine a besoin d'une solution d'hébergement **gratuite ou très peu coûteuse (< 5 €/mois)** capable de faire tourner les 4 conteneurs du MVP (~2,0 à 3,2 Go de RAM avec l'ETL mensuel).

Or, les deux meilleures options du marché pour un étudiant reposent sur **deux architectures de processeur (CPU) différentes** :
- Les **VPS (Virtual Private Server, serveur virtuel privé loué chez un hébergeur cloud)** économiques classiques (Hetzner, OVHcloud, DigitalOcean via GitHub Student Developer Pack) utilisent principalement des processeurs **x86_64 (`linux/amd64`)** (ou ARM64 chez Hetzner CAX11).
- L'offre gratuite la plus généreuse du marché, **Oracle Cloud Infrastructure (OCI) "Always Free"**, fournit des machines virtuelles basées sur des processeurs **ARM Ampere A1 (`linux/arm64`)** offrant jusqu'à **4 OCPU et 24 Go de RAM gratuitement à vie**.

**Problème technique** : Si notre pipeline CI/CD (GitHub Actions) ne construit nos images Docker que pour `linux/amd64` (architecture du PC Windows d'Amine), ces images refuseront de démarrer (`exec format error`) sur une VM ARM64 Oracle Cloud ou Hetzner CAX !

---

## 2. Comparaison des options d'hébergement

| Critère | Option 1 : Oracle Cloud Always Free (VM ARM Ampere A1) | Option 2 : VPS Cloud Étudiant / Low-Cost (Hetzner CX22 / CAX11 ou DigitalOcean Student Pack) | Option 3 : PaaS gratuits éphémères (Render Free / Streamlit Community Cloud) |
| :--- | :--- | :--- | :--- |
| **Architecture CPU** | `linux/arm64` (Ampere Altra) | `linux/amd64` (Intel/AMD) ou `linux/arm64` (Hetzner CAX11) | Mutualisé (pas de Docker Compose complet) |
| **Ressources (RAM / CPU)** | **Jusqu'à 24 Go RAM / 4 OCPU** (4 Go / 2 OCPU suffisent largement) | **4 Go RAM / 2 vCPU** | 512 Mo RAM, base PostgreSQL supprimée après 30 à 90 jours |
| **Coût mensuel** | **0,00 € / mois (Always Free)** | **0,00 €** (crédits GitHub Student Pack 200 $) ou **~3,80 € / mois** (Hetzner) | 0,00 € mais **inadapté** |
| **Fidélité à l'architecture Docker Compose** | **100 %** (`docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d`) | **100 %** (`docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d`) | **Faible** : oblige à casser le `docker-compose.yml` en services dispersés et met l'API en veille (*cold start* de 50 s) |
| **Inconvénients / Risques** | Inscription Oracle parfois capricieuse (vérification de carte bancaire stricte) ; pénurie occasionnelle de capacité ARM dans certaines régions. | Coût de ~3,80 €/mois si les crédits étudiants sont épuisés. | Base SQL détruite régulièrement ; impossible de faire tourner le cron ETL + MLflow proprement. |

---

## 3. Décision

Nous retenons une **stratégie agnostique compatible à 100 % avec l'Option 1 (Oracle Cloud ARM64 Always Free — Cible privilégiée à 0 €) ET l'Option 2 (VPS x86_64 / ARM64 — Solution de repli immédiate)**, tout en écartant l'Option 3 :

> **Mise à jour 2026-11-10 (`ADR-008`)** : le job de build multi-architecture est retiré de la CI tant que l'hébergeur n'est pas choisi. Il sera réintroduit au Sprint 4 uniquement si la démo est hébergée sur une machine `arm64`.

1. **Construction d'images Multi-Architecture (`linux/amd64` + `linux/arm64`) dans la CI (`US-02`)** :
   - Dans le workflow GitHub Actions (`.github/workflows/ci.yml`), nous utilisons **`docker/setup-qemu-action`** (QEMU est un émulateur permettant de compiler du code ARM sur un serveur x86) et **`docker/setup-buildx-action`** (Docker Buildx est le moteur de construction avancé de Docker supportant plusieurs architectures simultanées).
   - Les images publiées sur **GitHub Container Registry (`ghcr.io`)** portent un manifeste multi-arch (`platforms: linux/amd64,linux/arm64`).
   - **Vérification des dépendances Python sur ARM64** : `PostgreSQL 16-alpine`, `Python 3.11-slim`, `LightGBM`, `scikit-learn`, `pandas`, `FastAPI` et `Streamlit` disposent tous de roues binaires pré-compilées (*manylinux aarch64 wheels*) sur PyPI, garantissant une construction rapide sans compilation C++ interminable.
2. **Surcharge de production (`docker-compose.prod.yml`), séparation des images par service et Reverse Proxy HTTPS (`Caddy`) au Sprint 4 (`US-16` — MVP)** :
   - L'hébergement public en ligne (HTTPS) fait partie intégrante du **Cœur MVP (Sprint 4 — `US-16`)**, et non du Sprint 5 Bonus.
   - Avant la mise en ligne au Sprint 4, la **dette technique identifiée dans `ADR-001`** (image unique `agriprix-app:latest` embarquant toutes les dépendances et les outils de dev `pytest`/`ruff`) est résorbée en séparant les cibles du `Dockerfile` par service (`runtime-api`, `runtime-dashboard`, `runtime-mlflow`, `runtime-jobs`) sans outils de développement dans les images de runtime.
   - En production sur la VM (Oracle ARM ou VPS), un fichier `docker-compose.prod.yml` ajoute un conteneur ultra-léger **Caddy (`caddy:2-alpine`, ~30 Mo de RAM)** agissant comme **Reverse Proxy** (serveur frontal qui reçoit le trafic Internet HTTPS sur le port 443, renouvelle automatiquement les certificats TLS Let's Encrypt, et redirige les requêtes vers Streamlit ou FastAPI).
   - Les ports internes de PostgreSQL (`5432`) et MLflow (`5000`) sont liés uniquement à `127.0.0.1` en local et au réseau Docker interne (`expose`) en production, jamais ouverts sur Internet (`0.0.0.0`).
3. **Automatisation de la mise à jour mensuelle (`US-15` — Sprint 4 MVP)** :
   - Sur la VM d'hébergement, un **timer systemd / cron mensuel** exécute le 16 de chaque mois :
     `docker compose run --rm job-runner python -m src.pipeline.monthly_update`
     qui télécharge les nouveaux mois HDX/FAOSTAT, vérifie leur intégrité, met à jour l'entrepôt, réentraîne les modèles et rafraîchit les prévisions et anomalies.

---

## 4. Conséquences

### Positives
- **Liberté totale de déploiement au Sprint 4** : Que le compte Oracle Cloud Always Free d'Amine soit validé (`arm64`) ou qu'il préfère utiliser un VPS GitHub Student Pack / Hetzner (`amd64` ou `arm64`) ou même un Mac Apple Silicon M1/M2/M3 (`arm64`), le même `docker compose up` fonctionne immédiatement sans modifier une seule ligne de Dockerfile.
- **Compétence DevOps très valorisée** : La maîtrise de `Docker Buildx` multi-architecture (`amd64`/`arm64`) et d'un reverse proxy TLS automatique est un marqueur technique fort en entretien.

### Négatives et Mitigations
- **Temps de build CI multi-arch sous QEMU** : Compiler une image `arm64` par émulation QEMU sur un runner GitHub Actions `amd64` gratuit peut prendre 3 à 5 minutes de plus. *Mitigation* : Nous utilisons le cache de couches GitHub Actions (`cache-from: type=gha`, `cache-to: type=gha,mode=max`) et nous ne déclenchons le push multi-arch complet vers `ghcr.io` que lors des fusions sur `main` ou des tags de version, tandis que les Pull Requests testent uniquement l'architecture native `linux/amd64` pour garder une CI ultra-rapide (< 2 min).
