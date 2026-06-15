# Security Policy

## Reporting

Do not open public issues for suspected vulnerabilities or exposed credentials. Report security concerns privately through the repository owner's GitHub profile.

Include the affected component, reproduction steps, impact, and any proposed mitigation. Reports will be acknowledged as soon as practical.

## Deployment Requirements

- Store Azure credentials and API access keys in a managed secret store.
- Configure explicit `CORS_ORIGINS`; never use a wildcard in production.
- Terminate TLS at the platform edge or trusted reverse proxy.
- Restrict database and log access to authorized operators.
- Establish retention and deletion controls appropriate for contract data.
- Run dependency and container scanning in the deployment environment.

The public GitHub Pages frontend contains no service credentials. Optional user-provided access tokens are held in browser session storage and are not exported.
