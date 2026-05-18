# ADR-001: Concurrent Execution Guard

## Status

Accepted — 2026-05-17

## Context

Sloubles-clics ou appuis répétés sur le bouton "Start" peuvent ouvrir plusieurs connexions WebSocket ou lancer plusieurs requêtes HTTP simultanées pour le même outil. La spec demande que le frontend empêche les exécutions concurrentes (spec-common.md OQ-020).

## Decision

Ajout d'un garde-fou dans les hooks `useWebSocket` et `useToolExecution` :

1. **useWebSocket** : `connect()` vérifie si un WebSocket est déjà ouvert (`readyState === OPEN`) avant d'en créer un nouveau.
2. **useToolExecution** : `execute()` utilise un ref `executingRef` pour bloquer les appels concurrents. Le flag est libéré dans un bloc `finally`.

## Consequences

- Plus de risque de double exécution côté frontend.
- Le backend peut toujours recevoir des requêtes concurrentes (ex: deux onglets) — il les traite normalement.
- Pas d'impact sur l'UX : un second clic pendant l'exécution est simplement ignoré.
