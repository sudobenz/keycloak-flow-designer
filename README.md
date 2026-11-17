# Keycloak Flow Designer — 1.2.5

Éditeur web pour concevoir, importer, contrôler et déployer des **Authentication Flows Keycloak**. L'éditeur suit le modèle natif de Keycloak : exécutions ordonnées, requirements et sous-flows Basic/Form. Il ne transpose pas artificiellement les graphes de transitions d'Authentik.

## Version 1.2.5 — correction de la compilation Vue

- Fermeture du bloc `<template v-if="selected">` dans `Designer.vue`, oublié avant le `v-else` du panneau des propriétés.
- Cette erreur de structure Vue empêchait la compilation du frontend.

## Version 1.2.4 — correction du build frontend

- Le build de production utilise directement Vite (`vite build`).
- Le contrôle TypeScript reste disponible séparément avec `npm run typecheck` et ne bloque plus la construction de l’image Docker.
- L’archive est fournie avec les fichiers à la racine, prêts pour Portainer.

## Nouveautés 1.2.2

- Correctif de création des sous-flows : utilisation des provider IDs Keycloak `basic-flow` / `form-flow`, et choix explicite du `FormAuthenticator` (par défaut `registration-page-form`).
- Les FormAuthenticators et les Form Actions sont présentés séparément : le premier rend le formulaire, les secondes sont les étapes à l'intérieur du `form-flow`.
- Import corrigé des sous-flows : Keycloak fournit leur alias via `displayName` et leur identifiant interne via `flowId` ; ces deux informations sont conservées pour les mises à jour.
- Validation du FormAuthenticator contre le catalogue `form-providers` du Realm avant déploiement.

- Suppression d'un élément depuis son nœud dans le canvas, depuis sa ligne dans l'arborescence ou depuis le panneau Propriétés. Les raccourcis `Suppr` / `Backspace` sont disponibles hors des champs de saisie.
- Annulation / rétablissement des modifications avec `Ctrl+Z`, `Ctrl+Y` ou `Ctrl+Maj+Z`.
- Choix de l'orientation du diagramme : haut vers bas ou gauche vers droite.
- Début et fin du flow visibles ; flèches orientées, entrée dans un sous-flow et liaison de retour vers l'étape suivante du parent.
- Ajout, duplication locale, réordonnancement et déplacement de composants dans l'arborescence.
- Alias et description éditables pour les flows racine et les sous-flows ; les exécutions authenticator ne possèdent pas d’alias/description REST modifiables.
- Les requirements d'un `form-flow` sont limités à `REQUIRED` et `DISABLED`. Le sous-flow « Forms » du Browser flow standard est un Basic flow et peut donc être `ALTERNATIVE`.
- La validation vérifie aussi les champs de configuration obligatoires même si la configuration locale est vide.

## Capacités Authentication Flow prises en charge

- Flows racine `basic-flow` et `client-flow`.
- Sous-flows `basic-flow` et `form-flow` imbriqués.
- Authenticator providers et client authenticator providers découverts sur l'instance cible.
- Conditions Keycloak et sous-flows conditionnels.
- Requirements et priorités des exécutions ; alias et descriptions des flows et sous-flows. Alias de configuration distinct pour les authenticator configs.
- Configuration d'authenticator créée, modifiée ou supprimée ; schéma de propriétés récupéré dynamiquement ; configuration JSON libre en complément.
- Authenticator Reference et Authenticator Reference Max Age pour l'intégration AMR OIDC.
- Import récursif, duplication d'un flow natif, duplication locale d'une exécution, comparaison, validation, export projet JSON/YAML KFD, sauvegarde avant mise à jour et tentative de compensation.
- Bindings de Realm : Browser, Registration, Direct Grant, Reset Credentials, Client Authentication, Docker Authentication et First Broker Login.

Le catalogue local sert uniquement à démarrer hors connexion. Le catalogue Keycloak de l'instance réelle est la référence : les providers et leurs schémas varient selon la version installée et les extensions SPI présentes.

## Modèle d'exécution et représentation du parcours

Les exécutions d'un même niveau sont séquentielles et leur priorité détermine l'ordre. Les flèches du canvas montrent cet ordre structurel. Une flèche ne signifie pas qu'un échec d'authenticator sera automatiquement redirigé vers une branche graphique : le comportement concret dépend du provider et de son résultat (`success`, challenge, échec, etc.). Les requirements `REQUIRED`, `ALTERNATIVE`, `DISABLED` et `CONDITIONAL` définissent la logique de traitement Keycloak ; `CONDITIONAL` s'applique aux sous-flows, pas aux exécutions authenticator.

Un sous-flow Basic peut être `REQUIRED`, `ALTERNATIVE`, `CONDITIONAL` ou `DISABLED`. Un `form-flow` n'accepte que `REQUIRED` ou `DISABLED` et référence un FormAuthenticator (par exemple `registration-page-form`) ; son contenu est constitué d'exécutions Form Action. Le sous-flow nommé « Forms » dans le Browser flow standard est un Basic flow, malgré son nom. Les choix de requirements exposés par Keycloak restent la référence. Voir `docs/KEYCLOAK-CAPABILITY-MATRIX.md`.

## Fonctions qui ne sont pas des exécutions Authentication Flow

Certains éléments Keycloak proches de l'authentification ne sont pas des étapes standards du graphe Authentication Flow :

- Les **Required Actions** sont des actions distinctes associées à un utilisateur ou déclenchées à la suite d'une authentification.
- Les **Form providers** et **Form Action providers** sont deux SPI distincts : un FormAuthenticator est attaché au sous-flow `form-flow`, tandis que les Form Action providers sont les exécutions placées à l'intérieur de ce sous-flow.
- Les **Identity Provider mappers**, protocol mappers, client policies et les paramètres d'Identity Providers sont des ressources séparées.
- Le **Post Login Flow** se configure au niveau de l'Identity Provider ; ce n'est pas un binding global de Realm.

KFD affiche les FormActionFactory disponibles lorsqu’un sous-flow `form-flow` est sélectionné, et les FormAuthenticatorFactory à titre informatif. La matrice documente les capacités et limites de la version.

## Fonctions et architecture

- Frontend Vue 3, TypeScript et Vue Flow ; thèmes clair et sombre.
- Backend Python FastAPI ; API documentée via OpenAPI.
- Authentification locale avec rôles administrateur, éditeur et lecteur.
- Connexion à plusieurs instances Keycloak avec `client_credentials`.
- Stockage de projets JSON ; chiffrement au repos des secrets des connexions et des paramètres provider marqués secrets.
- Déploiement Docker Compose / Portainer.

## Installation Docker

Linux :

```bash
bash scripts/init-env.sh
docker compose up -d --build
```

Windows PowerShell :

```powershell
.\scripts\init-env.ps1
docker compose up -d --build
```

Interface : `http://localhost:8080`  
API OpenAPI : `http://localhost:8080/api/docs`

Compte initial : `admin` avec le mot de passe défini dans `INITIAL_ADMIN_PASSWORD`. Changer ce mot de passe immédiatement après la première connexion.

## Connexion à Keycloak

1. Créer un client confidentiel et activer Service Accounts.
2. Attribuer au compte de service les permissions minimales nécessaires pour lire et gérer les Authentication Flows et leurs configurations.
3. Pour modifier les Flow Bindings, autoriser également la gestion des paramètres du Realm.
4. Enregistrer les URL Admin REST et token, l'identifiant client et le secret.
5. Tester la connexion et sélectionner le Realm cible.

Conserver la vérification TLS activée en production. Ne pas utiliser le compte administrateur global par défaut.

## Déploiement d'un flow

- La création d'un flow personnalisé et la mise à jour d'un flow existant sont deux opérations distinctes.
- Pour mettre à jour, importer d'abord le flow cible afin de conserver ses identifiants d'exécution.
- La modification d'un flow natif nécessite de le dupliquer.
- Les suppressions distantes doivent être autorisées explicitement ; les suppressions locales dans le projet ne sont pas immédiatement propagées à Keycloak.
- Un snapshot est conservé avant une mise à jour. L'API REST répartit le déploiement sur plusieurs appels : le rollback est une compensation best-effort, pas une transaction atomique.
- Les Flow Bindings changent immédiatement le comportement du Realm ; vérifier le résultat sur un Realm de laboratoire avant production.

Les exports JSON/YAML sont des manifests de projet KFD, pas des formats natifs universels d'import Keycloak.

## Limites à connaître

- La validation structurelle et la prévisualisation ne remplacent pas un test de connexion sur un Realm de laboratoire.
- Les providers tiers / personnalisés sont configurables dans la mesure où Keycloak les expose et où leur schéma de configuration est disponible. Sinon, le JSON libre est fourni, mais les exigences propres au SPI doivent être vérifiées par son éditeur.
- Les propriétés d'exécution que l'API ne permet pas de modifier sont affichées en lecture seule.
- La matrice fonctionnelle précise les ressources intégrées, les ressources distinctes et les fonctions non couvertes.

## Développement et vérification

Backend :

```bash
cd backend
python -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q
```

Frontend :

```bash
cd frontend
npm install
npm run build
```

Créer `frontend/.env.local` avec `VITE_API_URL=http://localhost:8000/api` pour le développement local.
