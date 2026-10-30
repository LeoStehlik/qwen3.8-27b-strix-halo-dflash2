# Security

The reference service binds to `127.0.0.1` and has no API authentication. This
is intentional for a single-user local agent.

Do not change the bind address to `0.0.0.0` or expose port 8080 through a router
without adding an authenticated reverse proxy, TLS, request-size limits and an
explicit network allowlist. The model endpoint can consume substantial compute
and accepts remote image URLs.

Keep Hugging Face and GitHub credentials outside the repository. The supplied
scripts do not read or store tokens themselves; the standard CLIs may use their
own credential stores.

Model files and runtime archives are excluded from Git. Verify them against the
recorded SHA-256 hashes before execution.

To report a security issue after publication, use the repository owner's
private GitHub security-reporting channel rather than a public issue.
