# Keycloak Flow Designer — 1.0.6

Éditeur web autonome pour concevoir, importer, valider et déployer des Authentication Flows Keycloak.

## Corrections 1.0.1 à 1.0.6

- Correction du typage TypeScript dans le déplacement des nœuds de l’arborescence.
- En 1.0.3, la gestion de session ne supprime plus le jeton sur tous les HTTP 401.
- En 1.0.4, les opérations Valider et Export utilisent l’identifiant renvoyé après la sauvegarde et s’arrêtent si celle-ci échoue.
- En 1.0.5, le canvas dispose de contrôles d’ajout directs, d’un catalogue local de composants utilisable hors connexion, d’une recherche et d’un ajout de Provider ID personnalisé.
- En 1.0.6, le modèle réactif Vue est déballé récursivement avant clonage, ce qui corrige l’échec `DataCloneError` lors de l’ajout ou de la modification des composants.

## Fonctions livrées

- Interface Vue 3 / TypeScript avec Vue Flow : canvas, zoom, mini-carte, arborescence.
- Thèmes clair et sombre.
- Authentification locale : comptes administrateur, éditeur et lecteur ; changement de mot de passe ; activation/désactivation de comptes.
- Connexion à plusieurs instances Keycloak avec `client_credentials`.
- Stockage des projets en JSON ; secrets des connexions et propriétés providers marquées `secret` chiffrés au repos avec Fernet.
- Découverte des Realms, flows, authenticator providers et descriptions de configuration.
- Import récursif des flows et sous-flows dans le modèle JSON.
- Duplication des flows natifs Keycloak vers un flow personnalisé.
- Ajout d'exécutions et de sous-flux depuis le catalogue local ou dynamique, recherche de providers, ajout manuel d’un Provider ID personnalisé, exigences, ordre, configuration JSON et formulaires générés à partir des descriptions de providers.
- Validation, prévisualisation, sauvegarde de snapshot, déploiement REST et tentative de compensation en cas d'échec.
- Historique versionné des projets (50 versions conservées par projet) avec restauration réservée à l’administrateur ; journaux d’audit locaux.

## Installation Docker

Linux :
```bash
bash scripts/init-env.sh
# Le script crée .env, deux clés et un mot de passe admin aléatoire.
docker compose up -d --build
```

Windows PowerShell :
```powershell
.\scripts\init-env.ps1
docker compose up -d --build
```

Les scripts nécessitent Python 3 uniquement et refusent d'écraser un `.env` existant. Les clés Fernet sont générées avec la bibliothèque standard Python.

Interface : `http://localhost:8080`  
API OpenAPI : `http://localhost:8080/api/docs`  
API interne : `http://backend:8000/api/docs` depuis le réseau Docker.

Compte initial : `admin` avec le mot de passe défini dans `INITIAL_ADMIN_PASSWORD`. Changer ce mot de passe dans **Compte** dès la première connexion.

## Connexion à Keycloak

1. Créer un client confidentiel dans le Realm prévu pour le compte de service.
2. Activer Service Accounts.
3. Attribuer les rôles d'administration strictement nécessaires pour lire et gérer les Authentication Flows du Realm cible.
4. Ajouter dans l'application l'URL de base de l'Admin REST (par exemple `https://sso.example.net`) et l'URL token `https://sso.example.net/realms/<realm-technique>/protocol/openid-connect/token`.
5. Tester la connexion, puis sélectionner un Realm dans le Designer.

Ne pas utiliser le compte administrateur global par défaut. Garder la vérification TLS activée en production.

## Déploiement de flows

- **Créer** : crée un flow personnalisé avec l'alias saisi, puis ajoute les exécutions et sous-flux récursivement.
- **Mettre à jour** : réservé à un flow personnalisé existant, jamais à un flow intégré (`builtIn`). Il faut d’abord importer le flow cible dans le projet ; ses identifiants d’exécution servent à éviter les doublons. Un snapshot JSON du flow est enregistré avant modification.
- Le mode mise à jour ne supprime les exécutions distantes absentes du projet que lorsque « Autoriser les suppressions distantes » est coché. Les exports YAML sont des manifestes KFD documentés, pas un format YAML natif universel de Keycloak.
- La confirmation exige de saisir exactement l'alias cible. Seuls les comptes `admin` peuvent lancer le déploiement.
- En cas d'erreur, le backend tente une compensation à partir du snapshot. Une API REST multi-appels n'est pas atomique : une restauration complète ne peut être garantie si Keycloak ou le réseau reste indisponible pendant le rollback. Vérifier le rapport d'erreur et l'état du Realm.

## Stockage / sauvegarde

Tous les projets et journaux sont enregistrés sous `/app/data`, dans le volume Docker `designer_data`. Sauvegarder ce volume et conserver séparément `ENCRYPTION_KEY` et `SECRET_KEY`. La perte de `ENCRYPTION_KEY` empêche le déchiffrement des secrets des instances et des propriétés provider marquées secrètes. Les exports JSON/YAML contiennent les valeurs en clair et doivent être protégés.

## Développement local

Backend :
```bash
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```
Frontend :
```bash
cd frontend
npm install
npm run dev
```
Créer `frontend/.env.local` avec `VITE_API_URL=http://localhost:8000/api`.
Tests backend : `cd backend && pytest`.

## Exemple de départ

Les fichiers `examples/*.example.json` peuvent être importés dans le Designer. Deux modèles de départ sont aussi disponibles directement dans le sélecteur **Modèles de départ**. Ils sont illustratifs : vérifier les providers disponibles et adapter les requirements à votre parcours avant tout déploiement.

## Compatibilité

L'intégration utilise les endpoints Admin REST Authentication Management disponibles dans les versions prises en charge. La matrice multi-version doit être qualifiée contre les versions réellement exploitées, en particulier pour les SPI tiers et les descriptions de configuration. La détection dynamique dépend des métadonnées exposées par chaque provider. Les composants sans description sont accessibles via la configuration JSON avancée.

## Limites fonctionnelles connues

- L'éditeur représente la structure d'exécutions ordonnée de Keycloak ; il ne propose pas un moteur de branchement arbitraire. Les requirements sont ceux du moteur Keycloak.
- La simulation d'authentification réelle doit être effectuée sur un Realm de test avec de vrais navigateurs/clients ; la validation interne est structurelle.
- L'API d'administration Keycloak varie selon la version. Tester d'abord sur un Realm de laboratoire avant toute modification d'un flow utilisé en production.


## Version 1.0.6

- Correction du clonage du modèle dans l'éditeur : les Proxy réactifs Vue sont déballés récursivement avant `structuredClone`.
- Le clic sur un authenticator, un sous-flux ou le bouton d'ajout ne doit plus échouer avec `DataCloneError`.
- La même correction couvre les modifications, suppressions, déplacements, sauvegardes, validations et exports qui utilisent le clone du modèle.
