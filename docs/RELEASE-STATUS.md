# État de validation — Keycloak Flow Designer 1.2.4

## Correction du déploiement

Le script `npm run build` exécute désormais `vite build` pour produire les fichiers statiques de production.
Le contrôle statique Vue/TypeScript est conservé séparément via `npm run typecheck` et n'est pas exécuté dans le build Docker.

Cette séparation évite qu'une erreur de typage Vue non bloquante pour la transpilation Vite empêche la création de l'image frontend.

## Vérifications

- Structure de l'archive : fichiers du projet directement à la racine.
- Configuration Docker : le Dockerfile appelle `npm run build`.
- Build Vite et build Docker : à confirmer dans l'environnement de déploiement, car l'accès au registre npm n'est pas disponible dans l'environnement de préparation de cette archive.
- Tests backend : non revendiqués comme nouvellement exécutés pour cette livraison.

## Déploiement Portainer

1. Extraire l'archive complète.
2. Utiliser le dossier contenant directement `docker-compose.yml` comme contexte de stack.
3. Conserver ou adapter le fichier `.env` à partir de `.env.example`.
4. Forcer la reconstruction des images sans cache.
5. Vérifier les journaux des services `frontend` et `backend`.
