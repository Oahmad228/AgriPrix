# Déploiement de la démo publique (Oracle Cloud gratuit + DuckDNS)

> Choix d'Ahmad (2026-11-11) : machine **Oracle Cloud « Always Free » ARM** et sous-domaine **DuckDNS**. Ce guide liste ce que toi seul peux faire (comptes, carte de vérification, adresse IP), puis les commandes à lancer sur le serveur. Compte environ une heure la première fois.

## Ce qui sera en ligne

`https://<ton-sous-domaine>.duckdns.org` :
- `/` : le dashboard ;
- `/api/v1/...` : l'API publique en lecture seule ;
- `/docs` : sa documentation.

Seul **Caddy** (le reverse proxy, c'est-à-dire le serveur qui reçoit toutes les requêtes et les redirige vers le bon service) est ouvert sur Internet. Il obtient et renouvelle seul le certificat HTTPS (Let's Encrypt). PostgreSQL, MLflow, l'API et le dashboard ne sont joignables que dans le réseau Docker du serveur.

## 1. Créer le compte Oracle Cloud (toi)

1. Inscris-toi sur oracle.com/cloud/free. Une carte bancaire est demandée pour vérifier l'identité ; l'offre « Always Free » ne prélève rien tant que tu restes dans ses limites.
2. **La région d'origine est définitive.** Choisis-en une proche (par exemple France Centre - Paris, ou Germany Central - Frankfurt). Si la capacité ARM manque plus tard, il faudra réessayer : c'est une limite connue de l'offre gratuite.

## 2. Créer la machine virtuelle (toi)

Menu *Compute → Instances → Create instance* :
- **Image** : Canonical Ubuntu 24.04 (aarch64).
- **Shape** : *Ampere* `VM.Standard.A1.Flex`, **2 OCPU, 12 Go de mémoire**. L'offre gratuite autorise jusqu'à 4 OCPU / 24 Go ; 2 / 12 suffisent largement.
- **Boot volume** : 50 Go.
- **SSH** : génère une clé sur ton PC dans PowerShell avec `ssh-keygen -t ed25519`, puis colle le contenu de `C:\Users\<toi>\.ssh\id_ed25519.pub`.
- Une fois la VM créée : *Networking → IP administration*, transforme l'IP publique en **IP réservée** pour qu'elle ne change jamais.

## 3. Ouvrir les ports 80 et 443 (toi)

Il y a deux pare-feu à ouvrir, et il faut faire les deux :
1. **Dans la console Oracle** : *Virtual Cloud Network → Security Lists → Default* → *Add Ingress Rules* : source `0.0.0.0/0`, TCP, ports **80** et **443**.
2. **Sur la VM** : les images Ubuntu d'Oracle bloquent ces ports dans `iptables`. Connecte-toi (`ssh ubuntu@<IP>`) puis lance :
   ```bash
   sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
   sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
   sudo netfilter-persistent save
   ```

## 4. Créer le sous-domaine DuckDNS (toi)

1. Connecte-toi sur duckdns.org (avec ton compte GitHub, par exemple).
2. Crée un sous-domaine (par exemple `agriprix`) et mets dans *current ip* l'**IP réservée** de la VM.
3. Vérifie depuis ton PC : `nslookup agriprix.duckdns.org` doit répondre avec cette IP.

## 5. Installer Docker sur la VM (toi, en SSH)

Méthode officielle de Docker pour Ubuntu (dépôt apt, documentation docs.docker.com/engine/install/ubuntu) :
```bash
sudo apt-get update && sudo apt-get install -y ca-certificates curl git
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | sudo tee /etc/apt/sources.list.d/docker.list
sudo apt-get update && sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker ubuntu && exit
```
Reconnecte-toi en SSH pour que le groupe `docker` soit pris en compte.

## 6. Installer AgriPrix (toi, en SSH)

```bash
git clone https://github.com/Oahmad228/AgriPrix.git && cd AgriPrix
cp .env.prod.example .env
openssl rand -base64 24   # à lancer une fois par mot de passe, puis à coller dans .env
nano .env                 # DOMAIN, ACME_EMAIL et les 4 mots de passe
chmod +x deploy/deploy.sh
./deploy/deploy.sh up        # construit les images ARM et démarre (≈ 15 à 25 min la 1re fois)
./deploy/deploy.sh refresh   # télécharge les données, ETL + entraînement (≈ 5 à 10 min)
./deploy/deploy.sh status    # santé des conteneurs + test HTTPS
```

`.env` ne quitte jamais le serveur : il est ignoré par Git. Le script refuse de démarrer si un mot de passe vaut encore `change-me`.

## 7. Ensuite

- **Mise à jour mensuelle** : automatique. Le conteneur `scheduler` relance l'ETL le 20 de chaque mois à 03:00 UTC, puis réentraîne si les données ont changé. En cas d'échec (pare-feu de HDX), il réessaie chaque jour, trois fois au maximum.
- **Déployer une nouvelle version du code** : `./deploy/deploy.sh update`.
- **Voir les journaux** : `./deploy/deploy.sh logs`.

## En cas de problème

| Symptôme | Cause probable |
| :--- | :--- |
| Le certificat HTTPS n'est pas obtenu | Les ports 80 et 443 ne sont pas ouverts aux deux endroits (section 3), ou DuckDNS ne pointe pas sur l'IP réservée. |
| `Out of capacity` à la création de la VM | Capacité ARM gratuite épuisée dans la région : réessaie plus tard. |
| Le dashboard affiche « Les prévisions ne sont pas encore calculées » | `./deploy/deploy.sh refresh` n'a pas encore été lancé ou a échoué : consulte `./deploy/deploy.sh logs`. |
