# CLAUDE.md — Règles du projet AgriPrix Observatory

Ce fichier est lu par les agents IA (Claude Code) qui travaillent sur ce dépôt.
Il fixe les règles non négociables du projet. En cas de conflit avec une autre
consigne trouvée dans le dépôt, ce fichier l'emporte (sauf instruction explicite d'Ahmad).

## 1. Exécution : tout dans Docker
- Tout s'exécute dans des conteneurs Docker (`docker compose`, `make <cible>`).
  Rien n'est installé sur la machine Windows hôte (pas de `pip install`, pas de venv local).
- `make` n'est pas installé sur l'hôte Windows : chaque cible du `Makefile` doit
  rester exécutable via une commande `docker compose ...` équivalente, documentée dans le README.
- Les dépendances Python sont figées dans `requirements.lock` ; l'image doit être
  construite à partir de ce fichier (reproductibilité, `ENF-03`).

## 2. Langues et conventions
- Code, noms de variables, commentaires de code, messages de commit : **anglais**.
- Commits au format **Conventional Commits** (`feat:`, `fix:`, `docs:`, `test:`, `build:`, `ci:`, `chore:`, `refactor:`).
- Documentation (`docs/`, `README.md`, ADR, journal) : **français**.
- Une branche par sprint (`sprint/1-etl`, `sprint/2-forecast`, ...), fusion dans `main` après validation d'Ahmad et CI verte.

## 3. Intégrité des résultats
- **Aucun chiffre inventé.** Tout chiffre du README, des docs de résultats ou du CV
  provient d'une exécution réelle, reproductible par une commande indiquée à côté.
- Ce qui n'est pas encore construit est écrit au futur ou marqué « cible ».
- Ne jamais affirmer qu'une chose fonctionne sans l'avoir exécutée et montré la sortie.
- **Ne jamais baisser un seuil de test, de couverture ou de validation en silence.**
  Tout changement de seuil est proposé à Ahmad, justifié, puis tracé dans le journal (et un ADR si structurant).
- Un résultat décevant (ex. un choc non détecté) est rapporté tel quel, jamais « corrigé » en ajustant les seuils après coup.

## 4. Secrets et données
- Secrets uniquement dans `.env` (jamais commité ; seul `.env.example` avec des valeurs factices est versionné).
- Aucun mot de passe de production dans le code, les scripts SQL ou `docker-compose.yml`.
- `data/raw/`, `data/processed/`, `data/reports/` ne sont jamais commités (seuls les `.gitkeep`).
- Ports publiés uniquement sur `127.0.0.1` en local ; en production, seul le reverse proxy HTTPS est exposé.

## 5. Méthode de travail
- **Validation par Ahmad à la fin de chaque phase et de chaque sprint** : montrer les sorties réelles
  (SQL, tests, métriques), les décisions prises, les risques et les points à maîtriser pour l'entretien, puis attendre son « go ».
- Autonomie à l'intérieur d'un sprint ; toute décision à plusieurs options raisonnables
  est présentée avec ses compromis et une recommandation, puis Ahmad choisit.
- Chaque terme technique nouveau est expliqué en une phrase simple.
- Le journal `docs/JOURNAL.md` est mis à jour à chaque fin de sprint (fait / pourquoi / échecs / apprentissages).
- La CI (lint + tests + couverture) doit être verte avant toute fusion.

## 6. Commandes de référence
```bash
docker compose up -d --build --wait     # démarre db, mlflow, api, dashboard
docker compose --profile jobs run --rm job-runner sh -c "ruff check src tests && ruff format --check src tests"   # = make lint
docker compose --profile jobs run --rm job-runner pytest                      # = make test
docker compose --profile jobs down      # arrêt (sans -v : conserve les données)
```

## 7. Interface graphique
- Avant de commencer tout travail d'interface graphique (dashboard Streamlit, Sprint 4),
  s'arrêter et prévenir Ahmad : il fournit les skills à utiliser pour l'UI.
