# Gestion des sessions frontend — 1.0.3

## Comportement attendu

- `POST /api/auth/login` n'envoie pas un ancien jeton Bearer.
- Le jeton est conservé dans `localStorage` jusqu'à une déconnexion explicite ou une invalidation confirmée par `GET /api/auth/me`.
- Une réponse HTTP 401 sur une route métier ne supprime pas directement le jeton.
- Après un 401 sur une autre route, le frontend vérifie `/api/auth/me` :
  - 200 : la session locale reste active et l'erreur de la route concernée est affichée ;
  - 401 : la session est invalidée et l'utilisateur est renvoyé vers la connexion.

## Déploiement

Le frontend est servi comme fichiers statiques depuis l'image NGINX. Un simple redémarrage du conteneur ne met donc pas à jour le code embarqué : il faut reconstruire l'image frontend, puis recréer le conteneur.

Avec Docker Compose :

```bash
docker compose build --no-cache frontend backend
docker compose up -d --force-recreate backend frontend
```

Après redéploiement, effectuer un rechargement forcé du navigateur (`Ctrl+F5`) avant de tester la connexion.

## Contrôles réalisés dans l'environnement de génération

- `pytest -q` : 17 tests backend réussis.
- `python -m compileall -q app tests` : réussi.
- Transpilation syntaxique TypeScript des scripts `App.vue` et `api.ts` : réussie.

La compilation complète Vue/Vite et le build Docker n'ont pas été exécutés dans cet environnement : l'installation npm a dépassé le délai disponible et Docker/Podman n'est pas installé. Ils restent à valider lors du build Portainer.
