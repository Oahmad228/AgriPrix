# ADR-008 : Image Docker unique jusqu'au Sprint 3 et verrouillage effectif des dépendances

- **Statut** : Accepté — dette remboursée au Sprint 4 (voir §4)
- **Date** : 2026-11-10
- **Décideurs** : Ahmad & assistant IA (Claude Code)
- **Exigences liées** : `ENF-03` (reproductibilité), `US-01`, `US-02`, `US-16`
- **Remplace / précise** : le paragraphe « Dette technique » de [`ADR-001`](./001-surdimensionnement-architecture-devops.md)

---

## 1. Contexte

Au 2026-11-10, l'audit de reprise (Étape 0) a constaté par exécution :

1. **Le fichier `requirements.lock` n'était pas utilisé.** Le `Dockerfile` installait `pip install -e ".[dev]"` à partir des intervalles de versions de `pyproject.toml` (ex. `fastapi>=0.111,<1.0`). Une semaine après sa génération, **16 paquets** de l'image différaient déjà du lock (ex. `fastapi 0.162.0` dans le lock contre `0.162.2` installé). Deux builds à des dates différentes ne produisaient donc pas la même image.
2. **Le cache Docker était inefficace.** `COPY src` précédait l'installation des dépendances : toute modification du code relançait l'installation complète (build mesuré : **12 min**).
3. **Une seule image `agriprix-app:latest` (2,05 Go, mesurée par `docker images`)** sert `api`, `dashboard`, `mlflow` et `job-runner`, outils de développement (`pytest`, `ruff`) compris.

*Vocabulaire* : un **fichier de verrouillage** (*lock file*) liste la version exacte de chaque paquet installé, y compris les dépendances indirectes, pour que l'environnement soit identique à chaque build. Une **couche** (*layer*) Docker est une étape du build mise en cache : si ses entrées ne changent pas, Docker la réutilise sans la réexécuter.

## 2. Décision

1. **Verrouillage effectif** : l'image installe `pip install --no-deps -r requirements.lock`, puis exécute `pip check`.
   - `--no-deps` interdit à pip d'installer un paquet absent du lock ;
   - `pip check` fait échouer le build si le lock est incomplet ou incohérent.
   - Le projet lui-même est ensuite installé avec `pip install --no-deps -e .`.
2. **Image de base figée** : `python:3.11.18-slim` (au lieu de `python:3.11-slim`, qui change de version mineure sans prévenir).
3. **Ordre des couches** : `requirements.lock` est copié et installé **avant** le code. Un changement de code ne reconstruit plus que les dernières couches.
4. **Régénération du lock uniquement dans Docker** : `docker compose --profile jobs run --rm job-runner pip freeze --exclude-editable` (commande rappelée en tête du fichier). Toute mise à jour du lock fait l'objet d'un commit dédié `build(deps): ...`.
5. **Image unique conservée jusqu'au Sprint 3** (inchangé par rapport à `ADR-001`). Elle sera découpée au **Sprint 4, avant la mise en ligne**, en cibles multi-étapes : `runtime-api`, `runtime-dashboard`, `runtime-mlflow`, `runtime-jobs` et `dev`.
6. **Build multi-architecture retiré de la CI** jusqu'au choix de l'hébergeur (Sprint 4, `ADR-007`). L'émulation `arm64` par QEMU sur les runners gratuits est lente, et n'a d'utilité que si la démo est hébergée sur une machine ARM (Oracle Ampere).

## 3. Conséquences

### Positives (mesurées le 2026-11-10)
- `diff` entre `requirements.lock` et `pip freeze` dans l'image : **aucune différence (115 paquets)**.
- `pip check` : `No broken requirements found.`
- Rebuild après modification du code : **4,3 s** (couches de dépendances en cache), contre 12 min auparavant.

### Négatives / risques
- Le lock contient aussi les outils de dev : ils restent présents dans l'image de runtime jusqu'au Sprint 4.
- La mise à jour des dépendances devient manuelle (régénération du lock). C'est voulu : aucune mise à jour silencieuse.
- Image toujours lourde (2,05 Go) : temps de téléchargement plus long sur le serveur de démo tant que le découpage du Sprint 4 n'est pas fait.

### Critère de remboursement de la dette (Sprint 4)
- Les images `runtime-api` et `runtime-dashboard` ne contiennent ni `pytest`, ni `ruff`, ni `lightgbm`. Ce sera vérifié par un test automatique (`pip show` doit échouer pour ces paquets).
- La taille de chaque image sera mesurée et reportée ici.

## 4. Mise à jour du 2026-11-11 (Sprint 4) : dette remboursée

Le découpage a été fait avant la mise en ligne, comme prévu : une image par service, construite à partir d'un sous-ensemble exact du lock. Mesures : API **459 Mo**, dashboard 1,19 Go, MLflow 1,46 Go, jobs 1,59 Go, dev 2,06 Go (contre 2,05 Go pour l'image unique). Ni `pytest`, ni `ruff`, ni `lightgbm` dans les images de l'API et du dashboard (vérifié avec `pip show`). Le build `arm64` est réintroduit dans la CI, l'hébergeur retenu étant Oracle ARM. Détails : [`ADR-012`](./012-mise-en-production-oracle-duckdns-caddy.md).
