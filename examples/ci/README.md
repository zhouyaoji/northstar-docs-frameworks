# Alternative CI/CD configurations

These examples show how the Northstar documentation pipeline can be orchestrated
outside GitHub Actions. They are documentation artifacts and are not active in
this repository.

Both examples preserve the same portable contract:

1. Install pinned dependencies.
2. Validate the content manifest and source coverage.
3. Build all documentation renderers.
4. check the assembled site's local links and assets.
5. Retain `public/` as the immutable build artifact.
6. Deploy that artifact only from an approved default-branch build.

## Jenkins

`jenkins/Jenkinsfile` is a Declarative Pipeline example for a Jenkins
Multibranch Pipeline. The configured Linux agent must provide Node.js 22 and
Python 3.12. Copy or adapt the file to the location expected by the company's
Jenkins controller.

The `company-ci/deploy-docs.sh` command is deliberately a placeholder. Replace
it with the organization's approved artifact-promotion or deployment command.

## TeamCity

`teamcity/settings.kts` is a portable TeamCity Kotlin DSL example. To use it,
enable versioned settings in TeamCity and adapt or copy the example into the
repository's active `.teamcity/settings.kts` location. Match the DSL version to
the company's TeamCity server; the example uses `2025.11`.

The settings root is supplied by TeamCity when versioned settings are enabled.
The example expects a compatible Linux build agent and archives `public/` as a
TeamCity artifact. As with Jenkins, replace `company-ci/deploy-docs.sh` with the
company deployment integration.

Do not put credentials in either configuration. Use Jenkins Credentials
Binding, TeamCity password parameters, workload identity, or the organization's
secret manager.
