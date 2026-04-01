# tts_ci_cd
![Project logo](https://github.com/NASA-JPL-Teamtools-Studio/teamtools_documentation/blob/main/docs/images/tts_ci_cd.png)

## About Teamtools Studio

Teamtools Studio Utilities is part of JPL's Teamtools Studio (TTS).

TTS is an effort originated in JPL's Planning and Execution section to centralize shared repositories across missions. This benefits JPL by reducing cost through reducing duplicated code, collaborating across missions, and unifying standards for development and design across JPL.

Although Planning and Execution is primarily concerned with flight operations, the TTS suite has been generalized and atomized to the point where many of these tools are applicable during other mission phases and even in non-spaceflight contexts. Through our work flying space missions, we hope to provide tools to the open source community that have utility in data analysis or planning for any complex system where failure is not an option.

For more infomation on how to contribute, and how these libraries form a complete ecosystem for high reliability data analysis, see the [Full TTS Documentation](https://nasa-jpl-teamtools-studio.github.io/teamtools_documentation/).

## What is TTS CI/CD?

### Overview

TTS CI/CD is pretty much what it says on the tin. We're not trying to reinvent the wheel of how to do CI/CD here, but we recognize that there are many ways to implement CI/CD features and that a large project like the Teamtools Studio benifits significantly from standardization.

Historically at JPL adoption of unit testing, code scanning, and even packaging as libraries has been spotty and implemented differently across different projects and developers. This stems from the fact that teamtool developers are typically more operator than software engineer and either are not familiar with best practices around CI/CD or are sympathetic to the ideas but have not yet found the time to learn them well enough to cut through the noise to find a reasonable practice to follow. Even in cases where developers do implement CI/CD features, they tend to be very individual to the developer as doing the political work of convincing every project and developer to follow one's lead is a challenge in and of itself. This library represents the best effort to date to meet the political and technical challenges of getting everyone on board and doing it the same way.

This library goes hand in hand with the conventions encoded in tts_starter_kit, so all of the tools here should work off the shelf for any library started with that starter kit.

## Command Line Tools

A number of command line tools are provided in this library.

* *tts-git-dashboard*: Reports on the status of all git repos in a directory (defaults to current). Provides situational awareness across all libraries assuming developer has made changes across multiple. Shows the following:
    * Setuptools_scm version available locally
    * Branch checked out locally
    * Latest versions deployed to pypi and any artifactory locations configured in `.tts_config/deploy_locations.yaml`
    * Summary of git status
* *tts-dev-setup*: Clones, editably installs, and runs unit tests for any TTS library and its TTS dependencies (or all of them). Bootstrap to get a new development environment set up within ~5 minutes.
* *tts-doc-builder*: Builds `gh-pages` branch by checking out each active branch and every tag in the repo (except those configured to be ignored). Builds landing page for repo docs. Deploys to gh
* *tts-deploy-lib*: Deploys library to pypi or artifactory.

## Configuration

Some of the command line tools in this library (`tts-deploy-lib` and `tts-git-dashboard`) have an optional configuration file. It is used to include artifactory URLs and pypi keys that cannot be shared publically. An example is provided at (tts_config/README.md)[https://github.com/NASA-JPL-Teamtools-Studio/tts_ci_cd/blob/main/src/tts_ci_cd/tts_config/deploy_locations.yaml]