# Matrice fonctionnelle Keycloak — 1.2.3

Cette matrice distingue les fonctions relevant du moteur **Authentication Flows**, les ressources voisines de Keycloak et les limites de l'API REST. L'objectif est de couvrir les capacités que Keycloak expose pour un Authentication Flow, sans inventer un modèle de transition différent.

## Flows et sous-flows

| Capacité | Support KFD | Détail |
|---|---|---|
| Flow racine `basic-flow` | Oui | Flows d'authentification utilisateur habituels. |
| Flow racine `client-flow` | Oui | Authentification des clients ; catalogue de client authenticators séparé. |
| Sous-flow Basic | Oui | Imbrication récursive. |
| Sous-flow Form (`form-flow`) | Oui | Référence un FormAuthenticator (ex. `registration-page-form`) et contient des Form Action executions. |
| Alias / description du flow racine | Oui | Métadonnées de la représentation de flow. |
| Alias / description d'un sous-flow | Oui | Métadonnées du flow enfant. |
| Alias / description d'une exécution authenticator | Non | L’API d’exécution autorise la priorité et le requirement ; elle indique explicitement que les authenticator executions ne peuvent pas recevoir de nom/description. L’alias de configuration reste une propriété de l’Authenticator Config. |
| Création d'une exécution | Oui | Endpoint Admin REST d'ajout d'exécution. |
| Création d'un sous-flow | Oui | Endpoint Admin REST d'ajout de flow dans un flow parent. |
| Duplication d'un flow existant | Oui | Copie distante d'un flow vers un nouvel alias. |
| Import récursif | Oui | Exécutions, sous-flows, requirements, priorité, configuration et identifiants distants connus. |
| Suppression d'une exécution / sous-flow | Oui | Suppression locale immédiate ; propagation distante explicite lors de la mise à jour. |
| Réordonnancement | Oui | Priorité Keycloak et ordre dans le canvas / l'arborescence. |
| Mise à jour d'un flow personnalisé | Oui | Import préalable obligatoire, snapshot avant modification et compensation best-effort. |
| Modification directe d'un flow natif | Non | Dupliquer le flow natif puis modifier la copie. |

## Requirements et logique d'exécution

| Requirement | Support KFD | Sémantique Keycloak |
|---|---|---|
| `REQUIRED` | Oui | Chaque élément Required doit réussir, dans l'ordre ; un échec arrête le flow. |
| `ALTERNATIVE` | Oui | Une seule alternative réussie suffit au niveau concerné ; si des éléments Required suffisent, les alternatives peuvent ne pas être exécutées. |
| `DISABLED` | Oui | Élément ignoré pour déterminer le succès du flow. |
| `CONDITIONAL` | Oui, sous-flow uniquement | Si toutes les conditions sont vraies, le sous-flow se comporte comme Required ; si l'une est fausse ou s'il n'y a pas de condition, il est Disabled. |
| Requirements disponibles par provider | Oui | Les choix fournis par Keycloak lors de l'import sont conservés. En mode local, KFD utilise des choix par défaut prudents. |
| Conditions | Oui | Les authenticator providers `conditional-*` doivent être placés dans un sous-flow `CONDITIONAL` et leur requirement d'exécution doit être `REQUIRED`. |

Un sous-flow Basic peut être `REQUIRED`, `ALTERNATIVE`, `CONDITIONAL` ou `DISABLED`. Un flow référencé de type `form-flow` ne propose que `REQUIRED` et `DISABLED`. Le sous-flow « Forms » du Browser flow standard est un Basic flow, malgré son nom.

## Exécutions, providers et configuration

| Capacité | Support KFD | Détail |
|---|---|---|
| Authenticator providers | Oui | Découverte via Admin REST, y compris les extensions présentes sur l'instance. |
| Client authenticator providers | Oui | Découverte dédiée pour un flow `client-flow`. |
| Catalogue hors connexion | Partiel | Sélection de départ ; il ne prétend pas être exhaustif ni remplacer le catalogue serveur. |
| Provider ID personnalisé | Oui | Ajout libre, mais validation contre le serveur nécessaire avant déploiement. |
| Descriptions de configuration | Oui | Découverte du schéma `config-description/{providerId}`. |
| Propriétés obligatoires | Oui | Validation serveur, y compris lorsque le projet contient une configuration vide. |
| Types, listes, booléens, numériques, secrets, textes | Oui | Formulaire construit à partir des métadonnées du provider. |
| JSON de configuration libre | Oui | Pour les SPI dont le schéma n'est pas exposé ou pour les propriétés avancées. |
| Création / mise à jour / suppression de la configuration | Oui | Endpoints Admin REST de configuration d'authenticator. |
| Authenticator Reference / Max Age | Oui | Référence AMR facultative, à compléter par le mapper AMR OIDC côté client. |
| `level`, `index`, `userSetupAllowed` importés | Lecture seule | Métadonnées visibles ; ne pas les traiter comme modifiables si l'API d'exécution ne le permet pas. |
| Form providers / FormAuthenticators | Oui, sur un Form flow | SPI `FormAuthenticatorFactory`, découvert via `form-providers` et référencé par l'exécution qui relie le parent au sous-flow `form-flow` (ex. `registration-page-form`). |
| Form Action providers | Oui, dans un Form flow | SPI `FormActionFactory`, découvert via `form-action-providers` et ajouté comme exécution à l'intérieur du `form-flow`. Les schémas de configuration sont demandés via `config-description` quand l'instance les expose. |

## Représentation du parcours

Le canvas expose une représentation de lecture de l'ordre Keycloak :

- `DÉBUT` et `FIN` pour délimiter le parcours ;
- flèches orientées pour montrer la séquence et la priorité ;
- flèche violette d'entrée dans un sous-flow ;
- flèche violette en pointillés reliant la fin du sous-flow à l'étape suivante dans le flow parent ;
- orientation verticale (haut vers bas) ou horizontale (gauche vers droite) ;
- requirement visible sur chaque exécution et sous-flow.

Cette représentation n'ajoute pas de transitions libres. Keycloak n'expose pas dans l'Admin REST une définition de graphe utilisateur avec connecteurs personnalisés « succès », « échec », « timeout » ou « branche parallèle ». Le résultat de chaque authenticator dépend de son implémentation. Les flèches décrivent donc la succession structurelle, pas un simulateur d'exécution.

## Flow Bindings du Realm

| Binding | Support |
|---|---|
| `browserFlow` | Oui |
| `registrationFlow` | Oui |
| `directGrantFlow` | Oui |
| `resetCredentialsFlow` | Oui |
| `clientAuthenticationFlow` | Oui, avec flows `client-flow` |
| `dockerAuthenticationFlow` | Oui |
| `firstBrokerLoginFlow` | Oui |

La modification des bindings est réservée au rôle administrateur KFD et requiert les permissions Keycloak appropriées. La modification d'un binding change immédiatement le comportement du Realm.

## Ressources voisines, mais séparées

Ces éléments appartiennent à Keycloak mais ne sont pas des nœuds Authentication Flow standards :

- **Required Actions** : actions demandées à un utilisateur après ou pendant le parcours de compte ; elles ont leurs propres endpoints et leur propre cycle de vie.
- **Identity Provider mappers** et **Identity Provider settings** : ressources de fédération distinctes. Le First Broker Login Flow est un binding de Realm ; le Post Login Flow est configuré au niveau d'un Identity Provider.
- **Protocol mappers** : mapping des claims dans les tokens OIDC/SAML, distinct des exécutions du flow. La référence AMR du provider nécessite le mapper OIDC adapté côté client.
- **Client policies** : politiques de client distinctes, même si elles peuvent contribuer au choix du flow utilisé.
- **Form providers** : SPI de rendu de formulaire, pas des exécutions autonomes. **Form Action providers** : exécutions possibles à l’intérieur d’un `form-flow`, pas dans un Basic flow.

Ces ressources ne sont pas présentées comme si elles étaient des étapes de flow. Elles peuvent faire l'objet de modules d'administration séparés.

## Références officielles

- [Server Administration Guide — Authentication Flows](https://www.keycloak.org/docs/latest/server_admin/#_authentication-flows)
- [Server Administration Guide — Conditions in conditional flows](https://www.keycloak.org/docs/latest/server_admin/#_conditions)
- [Keycloak Admin REST API — Authentication flows and executions](https://www.keycloak.org/docs-api/latest/rest-api/)
- [RealmRepresentation — flow bindings](https://www.keycloak.org/docs-api/latest/javadocs/org/keycloak/representations/idm/RealmRepresentation.html)
- [AuthenticationExecutionInfoRepresentation](https://www.keycloak.org/docs-api/latest/javadocs/org/keycloak/representations/idm/AuthenticationExecutionInfoRepresentation.html)
