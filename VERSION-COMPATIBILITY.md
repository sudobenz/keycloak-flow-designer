# Exploitation

## Mise à jour

```bash
docker compose down
docker compose build --pull
docker compose up -d
```

Ne pas supprimer le volume `designer_data` pendant une mise à jour.

## Sauvegarde

```bash
docker run --rm -v keycloak-flow-designer_designer_data:/data -v "$PWD":/backup alpine \
  tar czf /backup/flow-designer-data-$(date +%F).tgz -C /data .
```
Conserver `SECRET_KEY` et `ENCRYPTION_KEY` séparément.

## Contrôles

```bash
docker compose ps
docker compose logs -f backend
docker compose logs -f frontend
curl -fsS http://localhost:8080/health
curl -fsS http://localhost:8080/api/openapi.json >/dev/null
```
Le health endpoint backend est sur le réseau interne Docker ; le healthcheck Compose le vérifie.

## Restauration

Arrêter la stack, réinjecter l'archive dans le volume `designer_data`, puis redémarrer. Vérifier que la même `ENCRYPTION_KEY` est disponible.


## Historique des projets

Depuis la bibliothèque des projets, ouvrir **Versions** pour consulter les versions précédentes. Un administrateur peut restaurer une version ; l'état courant est alors conservé comme nouvelle version avant restauration. Jusqu'à 50 versions modifiées sont conservées par projet.


## Snapshots Keycloak

Avant chaque mise à jour d'un flow personnalisé, un snapshot JSON est stocké dans `backups/` du volume. Les administrateurs peuvent les consulter dans **Sauvegardes** et exporter un snapshot. L'export contient les propriétés provider en clair ; le protéger comme un secret. Réimporter le JSON dans le Designer pour préparer un nouveau déploiement de restauration.
