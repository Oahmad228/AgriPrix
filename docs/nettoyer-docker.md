# Nettoyer Docker

Ménage fait le 2026-11-18 : **18,5 Go libérés** dans Docker. Les commandes ci-dessous sont sûres : elles ne touchent ni aux données (volumes) ni aux images dont AgriPrix a besoin.

| | Avant | Après |
| --- | --- | --- |
| Images | 10,43 Go | 4,76 Go |
| Conteneurs | 0,05 Mo | 0,04 Mo |
| Volumes | 664,5 Mo | 422,6 Mo |
| Cache de construction | 12,62 Go | 0 |
| **Total** | **23,71 Go** | **5,18 Go** |

Supprimés : images `agriprix-app`, `agriprix-jobs`, `agriprix-hf`, `debian`, `caddy`, `alpine`, le conteneur `agriprix-oci-retry` et son image `oci-cli` (option Oracle pas encore choisie), le cache de construction, 3 anciens volumes PostgreSQL sans nom du 11 novembre, `agriprix_raw_data` (remplacé par le dossier `data/`), `agriprix_caddy_config` et `agriprix_caddy_data`. Gardé à part : `n8n_data` (autre projet). Vérifié après : 343 079 observations dans la base, API et tableau de bord en ligne, 238 tests réussis.

## Ce qu'AgriPrix utilise (à garder)

| Élément | Rôle |
| --- | --- |
| images `agriprix-api`, `agriprix-dashboard`, `agriprix-mlflow`, `agriprix-dev` | API, tableau de bord, MLflow, tâches et tests (`docker-compose.yml`) |
| image `agriprix-research` | piste de recherche (branche `research/regime-shift`) |
| image `postgres:16-alpine` | base locale |
| volume `agriprix_pgdata` | **la base locale** (343 079 observations) |
| volume `agriprix_mlflow_artifacts` | runs et modèles MLflow |
| réseau `agriprix_network` | réseau du compose |
| volume `n8n_data` | **autre projet (n8n)**, gardé |

## 1. Voir la place prise (sans rien changer)

```powershell
docker system df
```

```powershell
docker system df -v
```

## 2. Ménage sûr (à refaire quand on veut)

Conteneurs arrêtés :

```powershell
docker container prune -f
```

Images sans nom (`<none>`), restes d'anciennes constructions :

```powershell
docker image prune -f
```

Cache de construction (le plus gros ; la prochaine construction d'image sera simplement plus longue) :

```powershell
docker builder prune -a -f
```

Réseaux inutilisés :

```powershell
docker network prune -f
```

Une image précise qui ne sert plus (exemple) :

```powershell
docker image rm agriprix-hf:local
```

**À ne jamais lancer sans réfléchir** : `docker system prune -a --volumes` et `docker volume prune`. Ils suppriment aussi les volumes, donc la base locale et les runs MLflow, sans retour possible.

## 3. Rendre la place à Windows (compacter le disque virtuel)

Le ménage libère la place *dans* le disque virtuel de Docker Desktop, mais le fichier ne rétrécit pas tout seul. Sur ce PC (WSL 2) : `C:\Users\Oahma\AppData\Local\Docker\wsl\disk\docker_data.vhdx`, 23,24 Go le 2026-11-18 pour environ 6,7 Go réellement utilisés.

1. Dans Docker Desktop : **Quit Docker Desktop** (icône dans la barre des tâches, clic droit).
2. Ouvrir **PowerShell en administrateur** et arrêter WSL :

   ```powershell
   wsl --shutdown
   ```

3. Vérifier que plus rien ne tourne (la liste doit montrer `Stopped`) :

   ```powershell
   wsl --list --verbose
   ```

4. Compacter le disque (outil Hyper-V, présent sur Windows 11 Pro) :

   ```powershell
   Optimize-VHD -Path "$env:LOCALAPPDATA\Docker\wsl\disk\docker_data.vhdx" -Mode Full
   ```

   Si `Optimize-VHD` n'existe pas, même chose avec `diskpart` (en administrateur) :

   ```text
   diskpart
   select vdisk file="C:\Users\Oahma\AppData\Local\Docker\wsl\disk\docker_data.vhdx"
   attach vdisk readonly
   compact vdisk
   detach vdisk
   exit
   ```

5. Relancer Docker Desktop, puis vérifier le projet :

   ```powershell
   docker compose up -d --wait
   ```

Compter quelques minutes. Ne pas interrompre la compaction.
