# Hausie Add-ons Repository

This repository is the source of truth for the public Home Assistant add-on.

Public repository:

```text
https://github.com/Haussie-au/hausie_app_homeassistant
```

Expected published structure:

```text
hausie-addons/
  repository.yaml
  hausie/
    config.yaml
    Dockerfile
    run.sh
    requirements.txt
    README.md
    DOCS.md
    CHANGELOG.md
    hausie_addon/
```

Home Assistant users add the repository URL under:

```text
Settings -> Add-ons -> Add-on Store -> Repositories
```

Then install:

```text
Hausie App
```

## Release Flow

1. Update the add-on code directly in `hausie/`.
2. Bump `hausie/config.yaml` version.
3. Commit and push to `Haussie-au/hausie_app_homeassistant`.
4. Home Assistant users get the update from `hausie/config.yaml`.

## Development vs Production

Local testing:

```text
Use the internal deploy tooling from the sibling `hausie` repository
```

Production:

```text
Home Assistant add-on repository
```

This repository stays public-ready. SSH deploy scripts and local-only tooling live in the internal `hausie` repository.

## AWS deployment clarification

This repository is **not deployed as an application on AWS EC2**. Production
distribution happens through the public GitHub Home Assistant add-on repository;
Home Assistant downloads and builds the version declared in
`hausie/config.yaml`.

AWS hosts the separate Hausie cloud API used by the add-on. Before publishing a
release, confirm that the add-on's cloud URL/configuration targets the intended
production API and that the API is deployed from the `hausie` repository. Never
place AWS credentials, cloud tokens, Home Assistant tokens, MQTT passwords, or
customer credentials in this public repository.

### Production release checklist

1. Make and test the add-on changes in `hausie/`.
2. Run the repository test suite applicable to the change.
3. Update `hausie/CHANGELOG.md`.
4. Bump `version` in `hausie/config.yaml`; Home Assistant uses this value to
   detect an update.
5. Commit and push the reviewed release to the default branch.
6. Refresh the repository in a non-production Home Assistant instance, install
   or update the add-on, and verify startup, ingress UI, cloud connectivity,
   logs, and upgrade behavior.
7. Only then promote/use the release on customer installations.

Local device testing uses the internal script from the sibling `hausie`
checkout:

```powershell
./scripts/deploy_public_addon_to_pi.ps1
```

That SSH workflow is for testing and is not the production release mechanism.

### Rollback

Publish a new patch version containing the revert/fix. Do not silently replace
the contents of an already published version because Home Assistant clients may
have cached or installed it. Verify the patch release on a test instance before
customer rollout.
