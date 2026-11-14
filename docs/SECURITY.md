# Sécurité

- Déployer derrière un reverse proxy HTTPS.
- Définir des secrets aléatoires uniques dans `.env`.
- Générer une clé Fernet avec `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
- Sauvegarder la clé Fernet hors du conteneur ; sa perte empêche de relire les secrets d'instances.
- Restreindre l'accès réseau à l'API et à l'interface.
- Utiliser un compte de service Keycloak avec privilèges minimaux.
- Ne pas désactiver la validation TLS en production.
- Sauvegarder régulièrement le volume `designer_data`.
- Modifier le mot de passe initial.
- Prévoir rate limiting, politique de verrouillage, rotation des secrets et audit centralisé avant exposition multi-utilisateur.
