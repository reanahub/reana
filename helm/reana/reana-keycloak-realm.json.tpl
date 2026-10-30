{
  "realm": {{ .Values.keycloak.realm | toJson }},
  "enabled": true,
  "sslRequired": "external",
  "roles": {
    "realm": [
      {
        "name": {{ required "keycloak.required_role must be set when bundled development Keycloak is enabled" .Values.keycloak.required_role | toJson }}
      },
      {
        "name": "reana:admin"
      },
      {
        "name": "offline_access"
      }
    ]
  },
  "clients": [
    {
      "clientId": {{ .Values.keycloak.web_client_id | toJson }},
      "enabled": true,
      "publicClient": false,
      "secret": {{ .Values.secrets.auth.REANA_AUTH_WEB_CLIENT_SECRET | toJson }},
      "standardFlowEnabled": true,
      "redirectUris": [
        "{{ include "reana.public_url" . }}/api/oauth/callback"
      ],
      "attributes": {
        "post.logout.redirect.uris": "{{ include "reana.public_url" . }}"
      },
      "protocolMappers": [
        {
          "name": {{ required "keycloak.roles_claim must be set when bundled development Keycloak is enabled" .Values.keycloak.roles_claim | toJson }},
          "protocol": "openid-connect",
          "protocolMapper": "oidc-usermodel-realm-role-mapper",
          "config": {
            "claim.name": {{ required "keycloak.roles_claim must be set when bundled development Keycloak is enabled" .Values.keycloak.roles_claim | toJson }},
            "jsonType.label": "String",
            "multivalued": "true",
            "access.token.claim": "true",
            "userinfo.token.claim": "true",
            "id.token.claim": "true"
          }
        },
        {
          "name": "reana-audience",
          "protocol": "openid-connect",
          "protocolMapper": "oidc-audience-mapper",
          "config": {
            "included.custom.audience": {{ .Values.keycloak.audience | toJson }},
            "access.token.claim": "true",
            "id.token.claim": "false"
          }
        },
        {
          "name": "email",
          "protocol": "openid-connect",
          "protocolMapper": "oidc-usermodel-property-mapper",
          "config": {
            "user.attribute": "email",
            "claim.name": "email",
            "jsonType.label": "String",
            "access.token.claim": "false",
            "userinfo.token.claim": "true",
            "id.token.claim": "true"
          }
        }
      ]
    },
    {
      "clientId": {{ .Values.keycloak.cli_client_id | toJson }},
      "enabled": true,
      "publicClient": true,
      "standardFlowEnabled": true,
      "defaultClientScopes": [
        "basic",
        "acr",
        "profile",
        "email",
        "roles",
        "web-origins"
      ],
      "optionalClientScopes": [
        "offline_access"
      ],
      "redirectUris": [
        "http://localhost/*",
        "http://127.0.0.1/*"
      ],
      "attributes": {
        "oauth2.device.authorization.grant.enabled": "true",
        "pkce.code.challenge.method": "S256"
      },
      "protocolMappers": [
        {
          "name": {{ required "keycloak.roles_claim must be set when bundled development Keycloak is enabled" .Values.keycloak.roles_claim | toJson }},
          "protocol": "openid-connect",
          "protocolMapper": "oidc-usermodel-realm-role-mapper",
          "config": {
            "claim.name": {{ required "keycloak.roles_claim must be set when bundled development Keycloak is enabled" .Values.keycloak.roles_claim | toJson }},
            "jsonType.label": "String",
            "multivalued": "true",
            "access.token.claim": "true",
            "userinfo.token.claim": "true",
            "id.token.claim": "true"
          }
        },
        {
          "name": "reana-audience",
          "protocol": "openid-connect",
          "protocolMapper": "oidc-audience-mapper",
          "config": {
            "included.custom.audience": {{ .Values.keycloak.audience | toJson }},
            "access.token.claim": "true",
            "id.token.claim": "false"
          }
        },
        {
          "name": "email",
          "protocol": "openid-connect",
          "protocolMapper": "oidc-usermodel-property-mapper",
          "config": {
            "user.attribute": "email",
            "claim.name": "email",
            "jsonType.label": "String",
            "access.token.claim": "false",
            "userinfo.token.claim": "true",
            "id.token.claim": "true"
          }
        }
      ]
    }
  ]
}
