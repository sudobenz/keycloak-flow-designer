# Sécurité

- Placer l'application derrière un reverse proxy HTTPS.
- Régénérer `SECRET_KEY` et `ENCRYPTION_KEY` avant tout usage réel.
- Conserver la clé Fernet hors du volume applicatif et dans un coffre de secrets adapté.
- Sauvegarder ensemble les fichiers de données chiffrés et les clés correspondantes.
- Utiliser un client confidentiel dédié Keycloak avec les permissions minimales nécessaires.
- Garder `verify_tls=true` ; ne désactiver TLS qu'en laboratoire.
- Ne pas exposer directement le backend au réseau utilisateur ; Compose n'expose que le frontend.
- Le frontend ne reçoit jamais les secrets client Keycloak.
- Les valeurs de configuration marquées `secret` dans les descriptions de providers Keycloak sont chiffrées dans les projets et snapshots JSON au repos avec `ENCRYPTION_KEY`. Les propriétés dont le provider n’expose pas de métadonnées `secret` ne peuvent pas être identifiées automatiquement.
- Les comptes locaux utilisent scrypt avec sel unique ; les mots de passe nécessitent au moins 12 caractères.
- Le login applique une limite de cinq échecs par utilisateur et adresse IP sur dix minutes, en mémoire dans le processus. Elle ne remplace pas un contrôle partagé si plusieurs workers sont utilisés.
- Les JWT ont une durée de vie de huit heures. La désactivation d’un compte bloque les requêtes suivantes, mais un changement de mot de passe ne révoque pas instantanément les jetons déjà émis.
- L'audit conserve des événements de sécurité et de déploiement, sans jetons ni secrets.
- Avant exposition internet-facing : ajouter un rate limiting au reverse proxy/WAF, sauvegarde externalisée, rotation de clés, supervision et test de sécurité applicatif.


## Exports de projets

Les exports JSON et YAML restituent volontairement les valeurs secrètes en clair afin de rester réutilisables. Traiter ces exports comme des secrets : droits d’accès restreints, stockage chiffré et nettoyage après transfert. Ne pas les committer dans Git.
