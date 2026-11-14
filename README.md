# Keycloak Flow Designer

Application web autonome de conception de workflows d'authentification Keycloak.

## État du livrable

Cette archive contient un socle exécutable : interface Vue 3/Vue Flow, API FastAPI, authentification locale, stockage JSON, gestion des instances Keycloak, découverte des realms/flows et modèle de projet indépendant de Keycloak.

Le déploiement distant des flows est volontairement protégé : l'API propose la connexion et la lecture, mais le moteur de déploiement complet (création ordonnée, configuration SPI, diff transactionnel et restauration) doit être validé sur des versions Keycloak réelles avant activation. Il n'est pas présenté comme opérationnel dans cette première livraison.

## Démarrage

```bash
cp .env.example .env
# Générer deux secrets distincts :
python -c "import secrets; print(secrets.token_urlsafe(48))"
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Reporter le premier dans SECRET_KEY et le second dans ENCRYPTION_KEY.
# Définir également INITIAL_ADMIN_PASSWORD.
docker compose up -d --build
```

Interface : http://localhost:8080  
API : http://localhost:8000/docs

Identifiant initial : `admin`  
Mot de passe : valeur de `INITIAL_ADMIN_PASSWORD` dans `.env`.

Changez le mot de passe dès la première connexion. L'application est prévue pour être placée derrière HTTPS en production.

## Architecture

- `frontend/` : Vue 3, TypeScript, Vue Flow, Pinia.
- `backend/` : FastAPI, Pydantic, adaptateur REST Keycloak.
- `data/` : projets, instances et données locales persistées dans un volume Docker.

## Limites à connaître

- L'authentification locale est une authentification applicative minimale. Pour une exposition en production, ajouter limitation de tentatives, politique de mots de passe, rotation et sauvegarde de la clé de chiffrement.
- Les secrets des instances sont chiffrés avec Fernet. `ENCRYPTION_KEY` doit être sauvegardée hors du conteneur : sa perte rend les secrets enregistrés illisibles.
- La découverte des providers dépend des endpoints et métadonnées exposés par la version et les extensions installées.
- Le modèle de graphe conserve une structure hiérarchique. Les arêtes graphiques servent à la visualisation ; elles ne définissent pas une logique de branchement arbitraire dans Keycloak.
- Les endpoints d'administration Keycloak varient selon les capacités disponibles. Tester chaque version ciblée dans une matrice d'intégration avant déploiement en production.

## Développement local

Backend :
```bash
cd backend
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Frontend :
```bash
cd frontend
npm install
npm run dev
```

Configurer `VITE_API_URL=http://localhost:8000` dans `frontend/.env.local`.

## Sauvegarde

Sauvegarder le volume `designer_data` et conserver séparément les valeurs `SECRET_KEY` et `ENCRYPTION_KEY`.
