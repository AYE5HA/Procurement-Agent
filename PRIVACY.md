# Privacy and Data Handling

Contract text may contain confidential commercial information, personal data, or regulated information. Operators are responsible for configuring an approved hosting environment before processing such content.

The application stores completed analyses in the configured SQLite database. The repository does not define a universal retention period because deployment requirements vary; operators must establish retention, deletion, backup, encryption, and access-control policies before production use.

When Azure AI is enabled, contract content and validated findings are transmitted to the configured Azure AI endpoint under the operator's Azure agreement and data controls.

The GitHub Pages frontend does not include analytics or third-party tracking scripts. An optional API access token is stored only in browser session storage.
