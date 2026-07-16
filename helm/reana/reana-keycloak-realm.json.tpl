{
  "realm": "{{ .Values.keycloak.realm }}",
  "enabled": true,
  "sslRequired": "none",
  "roles": {
    "realm": [
      {
        "name": "reana:user"
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
      "clientId": "{{ .Values.keycloak.web_client_id }}",
      "enabled": true,
      "publicClient": false,
      "secret": "{{ .Values.secrets.auth.REANA_AUTH_WEB_CLIENT_SECRET }}",
      "standardFlowEnabled": true,
      "redirectUris": [
        "https://{{ .Values.reana_hostname }}{{ if ne (int .Values.reana_hostport) 443 }}:{{ .Values.reana_hostport }}{{ end }}/api/oauth/callback"
      ],
      "protocolMappers": [
        {
          "name": "reana_roles",
          "protocol": "openid-connect",
          "protocolMapper": "oidc-usermodel-realm-role-mapper",
          "config": {
            "claim.name": "reana_roles",
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
            "included.custom.audience": "{{ .Values.keycloak.audience }}",
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
      "clientId": "{{ .Values.keycloak.cli_client_id }}",
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
          "name": "reana_roles",
          "protocol": "openid-connect",
          "protocolMapper": "oidc-usermodel-realm-role-mapper",
          "config": {
            "claim.name": "reana_roles",
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
            "included.custom.audience": "{{ .Values.keycloak.audience }}",
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
