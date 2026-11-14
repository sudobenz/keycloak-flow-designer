# Correctif 1.0.1 — compilation frontend

## Symptôme

`vue-tsc` signalait `findIndex`, `splice` et `forEach` comme absents de `never` dans `Designer.vue`, fonction `dropTree`.

## Cause

TypeScript ne peut pas toujours prendre en compte les affectations de variables locales effectuées depuis une fonction imbriquée (`locate`). Après le contrôle de nullité, les variables capturées pouvaient être réduites à `never`.

## Correction

La fonction récursive `findContainingList()` retourne directement `any[] | null`. Les variables `sourceList` et `targetList` sont initialisées à partir de ces valeurs de retour, puis contrôlées avant l'accès aux méthodes de tableau. Le déplacement reste limité à la même liste de frères dans l'arborescence.

## Vérifications

- 17 tests backend réussis (`pytest`).
- Le diagnostic TypeScript fourni pour `dropTree` est traité par cette correction.
- La compilation Vue/Vite complète n'a pas pu être relancée dans l'environnement de correction, car l'installation npm locale a expiré. Relancer `docker compose --progress plain build --no-cache frontend` dans l'environnement de déploiement.
