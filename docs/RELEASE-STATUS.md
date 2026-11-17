# État de validation — Keycloak Flow Designer 1.2.5

## Correction du build

La version 1.2.5 corrige une balise `<template>` manquante dans `frontend/src/components/Designer.vue`. Le bloc conditionnel `v-if="selected"` du panneau des propriétés n'était pas fermé avant son `v-else`.

Le script de production reste `vite build`. Le contrôle Vue/TypeScript est disponible séparément via `npm run typecheck`.

## Vérifications effectuées

- Structure des blocs `<template>` contrôlée après correction.
- Archive vérifiée : `docker-compose.yml` est à la racine et le frontend possède son Dockerfile.
- Le build réel Vite/Docker n'a pas pu être exécuté dans l'environnement de préparation, car le registre npm est inaccessible (résolution DNS `EAI_AGAIN`).

## Déploiement Portainer

1. Extraire l'archive complète.
2. Utiliser le dossier contenant directement `docker-compose.yml` comme contexte de stack.
3. Conserver ou adapter `.env` à partir de `.env.example`.
4. Forcer la reconstruction des images sans cache.
5. En cas d'échec, récupérer les lignes d'erreur détaillées qui précèdent la ligne `npm run build`.
