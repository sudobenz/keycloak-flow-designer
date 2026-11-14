# Intégration REST Keycloak

## Contrats utilisés

Les routes de gestion des flows, des exécutions, des providers d'authentification et des descriptions de configuration sont issues de l'Admin REST API officielle :

- `GET /admin/realms/{realm}/authentication/authenticator-providers`
- `GET /admin/realms/{realm}/authentication/config-description/{providerId}`
- `GET /admin/realms/{realm}/authentication/flows`
- `GET /admin/realms/{realm}/authentication/flows/{flowAlias}/executions`
- `POST /admin/realms/{realm}/authentication/flows`
- `POST /admin/realms/{realm}/authentication/flows/{flowAlias}/executions/execution`
- `POST /admin/realms/{realm}/authentication/flows/{flowAlias}/executions/flow`
- `PUT /admin/realms/{realm}/authentication/flows/{flowAlias}/executions`
- `POST /admin/realms/{realm}/authentication/executions/{executionId}/config`
- `POST /admin/realms/{realm}/authentication/executions/{executionId}/raise-priority`
- `POST /admin/realms/{realm}/authentication/executions/{executionId}/lower-priority`
- `DELETE /admin/realms/{realm}/authentication/executions/{executionId}`
- `POST /admin/realms/{realm}/authentication/flows/{flowAlias}/copy`

Les URLs et payloads doivent rester alignés sur la documentation officielle de la version réellement utilisée. Les opérations d'ajout d'exécution et de sous-flow acceptent un objet libre dans la définition OpenAPI ; le backend utilise les champs habituels `provider`, `alias`, `description`, `type`.

## Sémantique importante

Un flow est un conteneur ; les exécutions et sous-flows sont évalués dans l'ordre. Le canvas et les liens du designer visualisent cet ordre et la hiérarchie, ils ne constituent pas une logique de branchement générique. `REQUIRED`, `ALTERNATIVE`, `CONDITIONAL` et `DISABLED` ont une sémantique déterminée par Keycloak. Les conditions sont prévues dans des sous-flows conditionnels selon les règles Keycloak.

## Snapshot / compensation

Avant une mise à jour, le backend importe récursivement le flow dans un snapshot JSON. Si une étape de déploiement échoue, il tente de reconstruire l'arbre à partir de ce snapshot. Cette compensation est best-effort : l'Admin REST API ne fournit pas de transaction atomique couvrant toutes les mutations. Une restauration partielle est possible et doit être traitée comme incident de changement.

## Providers personnalisés

Les providers SPI installés sur le serveur apparaissent dans la découverte quand Keycloak les expose via `authenticator-providers`. La description de configuration est obtenue par `config-description/{providerId}`. Les propriétés non décrites ou non typées ne sont pas devinées ; elles restent éditables dans le JSON avancé.


## Migration entre instances / Realms

Les identifiants d'exécution Keycloak ne sont pas considérés comme portables. Si un projet possède une source distante différente de sa cible, le moteur peut tenter une correspondance ordonnée par providerId ou alias de sous-flow. Cette correspondance est heuristique : elle doit être vérifiée par la prévisualisation et un test en Realm de recette. Pour une mise à jour sur la même cible, les identifiants importés sont prioritaires ; un nœud nouvellement ajouté n'est jamais assimilé automatiquement à une exécution existante sur la seule base de son providerId.

## Rôles du compte de service

Créer un client confidentiel dédié et activer son compte de service. Attribuer les rôles du client `realm-management` au service account dans le Realm cible. Les noms et périmètres exacts des rôles disponibles évoluent avec les versions : les rôles courants incluent notamment `view-realm`, `manage-realm` et `realm-admin`, mais l’API Authentication Management peut exiger des droits de gestion spécifiques. Tester les opérations requises avec le minimum de privilèges ; si la délégation fine ne suffit pas, utiliser un compte de service limité au seul Realm concerné plutôt qu’un administrateur global. Ne pas activer `Full Scope Allowed` par défaut en production.

## Requirements et sous-flux conditionnels

Le designer limite par défaut les requirements d'une exécution authenticator à `REQUIRED`, `ALTERNATIVE` et `DISABLED`. `CONDITIONAL` est réservé aux sous-flux conditionnels. Les choix exposés par Keycloak pour une exécution importée sont conservés dans le projet et priorisés sur la liste de secours de l'interface.


## Provenance exigée pour une mise à jour

Le projet doit contenir `target.sourceFlowId`, ainsi que l'instance et le Realm sources. Une mise à jour sur la même instance/Realm est refusée si l'identifiant du flow source ne correspond pas au flow cible. Pour une migration vers une autre instance ou un autre Realm, les identifiants ne sont pas portables et la correspondance par provider/alias reste heuristique ; la prévisualisation est obligatoire.
