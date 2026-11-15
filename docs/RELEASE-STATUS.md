# État de validation — Keycloak Flow Designer 1.2.2

## Changements de cette livraison

- Suppression accessible dans le canvas, l'arborescence et le panneau Propriétés ; raccourcis de suppression, annulation et rétablissement.
- Choix du sens de lecture vertical ou horizontal ; début, fin, flèches séquentielles, entrée dans les sous-flows et retour vers le parent.
- Alias et description des sous-flows éditables ; retrait des champs alias/description sur les authenticator executions, non modifiables via l’API REST.
- Distinction stricte Basic/Form/Client : FormActionFactory dans `form-flow`, AuthenticatorFactory dans `basic-flow`, ClientAuthenticatorFactory dans `client-flow`.
- Création REST des sous-flows alignée sur les IDs `basic-flow` / `form-flow`, avec FormAuthenticator référencé et validé depuis `form-providers`.
- Import des sous-flows aligné sur `displayName` (alias) et `flowId` (identifiant interne) fournis par Keycloak ; récupération directe du flow enfant pour les mises à jour.
- Validation de configuration provider plus stricte : recherche des champs obligatoires même lorsque la configuration locale est vide ; un flow vide ne requiert pas le catalogue des providers.
- Matrice de fonctionnalités mise à jour avec distinction entre Authentication Flows et ressources Keycloak voisines.

## Résultats vérifiés dans l'environnement de préparation

- `cd backend && pytest -q` : **40 tests réussis** après ajout des tests FormAuthenticator et contrat REST de création des sous-flows.
- `python -m compileall -q backend` : réussi.
- Compilation syntaxique TypeScript du bloc `<script setup>` de `Designer.vue` par le compilateur TypeScript global : réussie.
- Build complet Vue/Vite : non exécuté ; les dépendances npm ne sont pas disponibles localement dans l'environnement de préparation et leur installation réseau avait échoué dans les essais précédents.
- Build Docker : non exécuté.
- Tests d'intégration avec un serveur Keycloak réel : non exécutés.

## Contrôles d'acceptation à exécuter sur la cible

1. Vérifier `http://<hôte>:<port>/health` : la version doit être `1.2.2`.
2. Créer un flow Basic vide, ajouter une exécution, puis la supprimer depuis le canvas, l'arborescence et le panneau Propriétés.
3. Vérifier l'annulation et le rétablissement avec `Ctrl+Z` / `Ctrl+Y`.
4. Passer de l'orientation verticale à horizontale et contrôler le sens des flèches.
5. Ajouter un sous-flow Basic contenant un sous-flow Basic `ALTERNATIVE` ; contrôler l'entrée et le retour vers l'étape suivante du parent.
6. Importer un flow réel, modifier l'alias et la description d'un sous-flow, vérifier le FormAuthenticator d'un `form-flow`, puis déployer sur un Realm de laboratoire et réimporter le flow.
7. Tester les exigences Required, Alternative, Disabled et Conditional ainsi que les champs provider obligatoires.
8. Vérifier les suppressions distantes uniquement avec la case d'autorisation activée et sur un flow de test.

Une validation navigateur et un test REST contre la version Keycloak réellement exploitée restent requis avant une mise en production.
