// Demonstration only: copy or adapt this file to .teamcity/settings.kts.
import jetbrains.buildServer.configs.kotlin.*
import jetbrains.buildServer.configs.kotlin.buildSteps.script
import jetbrains.buildServer.configs.kotlin.triggers.vcs

version = "2025.11"

project {
    buildType(NorthstarDocs)
}

object NorthstarDocs : BuildType({
    id("Northstar_Docs_Build")
    name = "Build and verify Northstar documentation"
    description = "Validates, renders, verifies, and packages all documentation sites"

    // Store the same immutable output directory used by GitHub Actions.
    artifactRules = "public/** => rendered-documentation"

    vcs {
        root(DslContext.settingsRoot)
        cleanCheckout = true
    }

    steps {
        script {
            name = "Install pinned dependencies"
            scriptContent = """
                npm ci --prefix sites/antora
                npm ci --prefix sites/docusaurus
                npm ci --prefix sites/redocly
                python -m pip install --requirement requirements.txt
            """.trimIndent()
        }
        script {
            name = "Validate content manifest and source parity"
            scriptContent = "python tools/validate-content.py"
        }
        script {
            name = "Render all documentation sites"
            scriptContent = "./tools/build-sites.sh"
        }
        script {
            name = "Check generated links and assets"
            scriptContent = "python tools/check-built-links.py"
        }
        script {
            name = "Deploy approved main-branch artifact"
            conditions {
                equals("teamcity.build.branch", "main")
            }
            // Company-owned example. Replace this with an approved TeamCity
            // deployment configuration or artifact-promotion integration.
            scriptContent = "./company-ci/deploy-docs.sh public"
        }
    }

    triggers {
        vcs {
            branchFilter = "+:*"
        }
    }

    requirements {
        contains("teamcity.agent.jvm.os.name", "Linux")
    }
})
