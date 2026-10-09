# Security Policy

## Supported Versions

Only the latest release line receives security updates and patches.

| Version | Supported |
| :--- | :--- |
| 0.1.x | Yes |
| < 0.1.0 | No |

## Reporting a Vulnerability

Do not report security vulnerabilities through public GitHub issues, discussions, or pull requests.

To report a vulnerability:
1. Use GitHub's private vulnerability reporting feature on this repository (`Security` tab $\rightarrow$ `Advisories` $\rightarrow$ `Report a vulnerability`).
2. Alternatively, send an encrypted disclosure report with reproduction steps to `security@agentgate.dev`.

### Report Contents

Include the following diagnostic information:
- Description of the defect or vulnerability.
- Minimal reproducible example or proof-of-concept payload.
- Affected components (e.g., AST inspector, HMAC verification, ApprovalGate state machine).
- Assessment of potential impact.

### Response Timeline

- **Initial Acknowledgement:** Within 48 hours of receipt.
- **Triage & Reproduction:** Within 5 business days.
- **Patch Release:** Coordinated disclosure following verified resolution.
