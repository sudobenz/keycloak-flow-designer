# Architecture technique

## Frontend

Vue 3 + TypeScript, Vue Flow pour le canvas, Axios pour l'API. Le canvas représente les exécutions au sein d'une arborescence de sous-flows. Les liens relient les frères dans l'ordre d'exécution ; ils ne codent pas une logique de branchement autonome.

## Backend

FastAPI expose une API REST interne. Les fonctions sont réparties entre :

- `keycloak.py` : client Admin REST et client-credentials ;
- `workflows.py` : import récursif, validation et comparaison ;
- `deployment.py` : synchronisation des exécutions, sauvegarde et compensation ;
- `project_security.py` : chiffrement des propriétés provider marquées secrètes dans les fichiers JSON ;
- `security.py` : comptes locaux, JWT et chiffrement Fernet ;
- `storage.py` : écriture JSON atomique et journal d'audit JSONL.

## Stockage

Le volume Docker `designer_data` contient `projects/`, `history/`, `instances/`, `users/`, `backups/` et `audit/`. L’historique conserve jusqu’à 50 versions modifiées par projet ; la restauration crée une nouvelle version au lieu d’effacer l’état courant. Les fichiers de projets sont en JSON. Les secrets de connexion Keycloak et les paramètres provider identifiés par `secret=true` sont chiffrés au repos. Les exports JSON/YAML restent lisibles et peuvent contenir des valeurs secrètes.

## Cycle de déploiement

1. Validation locale du projet.
2. Vérification des providers disponibles sur le Realm cible.
3. Lecture des flows cibles et détection de collision.
4. Snapshot avant mise à jour.
5. Création ou modification du flow racine.
6. Synchronisation récursive des exécutions et sous-flows.
7. Mise à jour des requirements, configurations et priorités.
8. Relecture depuis Keycloak et mise à jour du projet local.
9. En cas d'erreur, tentative de compensation.

Keycloak ne fournit pas de transaction atomique pour ce lot d'appels REST. La compensation est best-effort, pas une garantie de rollback transactionnel.
