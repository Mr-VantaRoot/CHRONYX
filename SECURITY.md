# Security policy

## Reporting a vulnerability

Please report security issues privately through GitHub's **Report a vulnerability** feature on the CHRONYX repository. If private vulnerability reporting is unavailable, contact the repository owner through the email listed on their GitHub profile. Do not post exploit details in a public issue until a fix or mitigation is available.

Include the affected version, operating system, steps to reproduce, and any relevant logs or screenshots. Do not include competition database contents or other personal data.

CHRONYX is a local, single-user desktop application. The HTTP service binds to `127.0.0.1:8765`, validates Host headers and browser Origins, and intentionally has no authentication. A process running as the same OS user can access local application data.
