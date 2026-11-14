# Intégration Keycloak

## Authentification distante

Utiliser un client confidentiel dédié avec `serviceAccountsEnabled=true` et les rôles d'administration strictement nécessaires. L'application utilise `client_credentials`. Ne pas utiliser le compte `admin` du Realm master comme identité d'intégration courante.

## Découverte

L'application interroge les endpoints Admin REST de la cible. Les flows et leurs exécutions sont exposés par les endpoints `authentication/flows` et `authentication/flows/{alias}/executions`. Les capacités de découverte de providers ne sont pas uniformes : l'application prévoit un catalogue de secours et doit afficher la provenance des données.

## Déploiement

Le déploiement complet n'est pas activé dans cette version. Avant de l'implémenter, il faut :
1. Capturer les payloads REST réels sur chaque version cible.
2. Créer un flow top-level de test.
3. Ajouter un subflow basic puis form.
4. Ajouter des exécutions natives et un authenticator SPI tiers.
5. Modifier requirements et priorités.
6. Vérifier les réponses et relire la représentation.
7. Tester les cas d'échec et la restauration.

Ne pas supposer que les appels REST multiples forment une transaction. Le futur moteur doit créer un snapshot, produire un plan explicite, exécuter les opérations séquentiellement, vérifier l'état final et tenter une compensation en cas d'échec.

## Sémantique

Keycloak évalue un flow selon sa structure, ses exécutions et leurs requirements. Les liens visuels ne doivent pas être convertis en branches conditionnelles arbitraires. Les sous-flux `basic` et `form` ont des comportements distincts.
