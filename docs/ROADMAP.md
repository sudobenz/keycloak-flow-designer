# Roadmap

## Livraison actuelle (socle 0.1)
- Interface française, thèmes clair/sombre.
- Authentification locale.
- Canvas Vue Flow et arborescence simplifiée.
- Catalogue de composants de départ et découverte distante best-effort.
- Projets JSON et validation structurelle.
- Connexion Keycloak par client_credentials.
- Lecture des realms, flows et exécutions.

## Prochaine étape obligatoire
- Modèle hiérarchique complet avec édition imbriquée des sous-flux.
- Import fidèle d'un flow Keycloak existant.
- Découverte/versioning des métadonnées de providers.
- Gestion de configuration par formulaire dynamique.
- Tests d'intégration Keycloak par version.

## Avant production
- Diff sémantique et plan de déploiement.
- Déploiement idempotent.
- Snapshot et compensation.
- Audit détaillé.
- RBAC local et gestion de comptes.
- Durcissement sécurité et tests de charge.
