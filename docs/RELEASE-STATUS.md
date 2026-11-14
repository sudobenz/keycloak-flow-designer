# État de validation de la livraison 1.0.0

## Contrôles exécutés dans l'environnement de génération

- Backend : `pytest -q` — 17 tests réussis.
- Python : `python -m compileall -q app tests` — réussi.
- Scripts TypeScript : transpilation syntaxique des blocs `<script setup>` et des fichiers `.ts` — réussie.
- Script Linux `scripts/init-env.sh` : testé dans un répertoire temporaire ; génération de `.env`, remplacement des placeholders et permissions `0600` — réussi.
- Génération des clés Fernet basée uniquement sur la bibliothèque standard Python — vérifiée.
- Protection des paramètres providers marqués `secret`, y compris dans les snapshots de flows imbriqués — testée.
- Historique de projets et restauration administrateur — test API réussi.
- Liste et export JSON des snapshots de déploiement — test API réussi.
- Endpoint d’audit protégé par le rôle administrateur ; affichage du journal dans l’interface.
- Modèles Browser de base et Kerberos/OTP conditionnel — validation structurelle des exemples réussie.
- Garde-fou de mise à jour : la provenance du flow importé doit correspondre à la cible sur la même instance/Realm — test réussi.

## Contrôles non exécutés

- Installation npm et compilation complète Vue/Vite : non exécutées. `npm install` a expiré dans l'environnement de génération ; aucun `node_modules` n'est inclus dans l'archive.
- Build Docker Compose : non exécuté car le moteur Docker/Podman n'est pas installé dans l'environnement de génération.
- Script Windows PowerShell : non exécuté, aucun interpréteur PowerShell n'est disponible.
- Intégration réelle à un serveur Keycloak : non exécutée. Les routes et payloads s'appuient sur l'Admin REST API documentée, mais chaque version cible et chaque SPI tiers doivent être qualifiés sur un Realm de recette.

## Conséquence

Le livrable contient le code source, les conteneurs, les scripts, les tests backend et la documentation. Il ne doit pas être considéré comme certifié en production tant que les contrôles non exécutés n'ont pas été passés dans l'environnement cible. Commencer par un déploiement de laboratoire et un Realm non critique.


## Correctif 1.0.3 — persistance de session frontend

- Le client Axios ne supprime plus le jeton local sur chaque réponse HTTP 401.
- Les tentatives de connexion `/auth/login` n'envoient plus un éventuel ancien jeton.
- Le chargement initial valide désormais la session avec `/auth/me` avant de charger les autres ressources.
- Un 401 provenant d'une autre route déclenche une nouvelle vérification de `/auth/me` ; la session n'est supprimée que si cette vérification confirme qu'elle est invalide.
- Les refus d'accès sur les autres routes sont affichés sans déconnecter automatiquement l'utilisateur.

### Contrôles du correctif 1.0.3

À exécuter avant validation de production : compilation frontend (`npm run build`), tests backend (`pytest -q`) et reconstruction des images via Portainer. L'intégration réelle doit ensuite être vérifiée avec une connexion utilisateur et une requête Keycloak volontairement refusée.
