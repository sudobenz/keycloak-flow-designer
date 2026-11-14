# Compatibilité Keycloak

L'application utilise le client REST générique et les contrats Authentication Management de l'Admin REST API. Elle détecte la version retournée par `/admin/serverinfo` lorsqu'elle est accessible. Les opérations utilisées sont documentées dans les références REST officielles 26.x et latest, mais aucune matrice ne doit être considérée certifiée sans tests sur les builds exacts.

| Ligne | Statut de cette livraison |
|---|---|
| Keycloak 26.1.x | Contrats REST vérifiés sur documentation versionnée ; recette réelle nécessaire |
| Keycloak 26.2.x–26.5.x | Compatibilité visée ; recette réelle nécessaire |
| Keycloak 26.6.x–26.8.x | Contrats présents dans documentation REST récente ; recette réelle nécessaire |
| Version majeure suivante | Non qualifiée |

Tester la découverte des providers, descriptions de configuration, sous-flows `basic` et `form`, requirements, authenticator SPI personnalisés, priorités, suppression, import et compensation. Les extensions tierces peuvent exposer des propriétés ou exigences particulières.
