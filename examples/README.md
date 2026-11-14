# Modèles de flows

- `browser-basic.example.json` : Cookie Alternative, puis formulaire Username/Password.
- `browser-kerberos-mfa.example.json` : Cookie et Kerberos en alternatives, puis formulaire avec sous-flow OTP conditionnel.

Ces fichiers sont des points de départ illustratifs. Les authenticator `auth-spnego`, `conditional-user-configured` et `auth-otp-form` doivent être présents sur la cible. Vérifier le comportement attendu et les requirements avec la version Keycloak réellement utilisée avant déploiement. Les alias proposés doivent être uniques dans le Realm.
