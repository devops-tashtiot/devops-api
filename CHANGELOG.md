# Changelog

All notable changes to this project will be documented in this file.

## [0.2.6] - 2026-07-12

### Bug Fixes

- *(bitbucket)* Sync must pick the syncable directory, not directories[0] ([f74a0cc](https://github.com/devops-tashtiot/devops-api/commit/f74a0ccb3e51b654071136e4338a7898d9d4c36f))

## [0.2.5] - 2026-07-12

### Bug Fixes

- *(bitbucket)* Use Crowd directory API for sync, doc real CI pipeline ([5d67b73](https://github.com/devops-tashtiot/devops-api/commit/5d67b739b8a683fef5bbe54f3fc62ec4d4c00014))

## [0.2.4] - 2026-07-12

### Bug Fixes

- *(jira)* Use Crowd directory API for user-dirs, not admin/user-directories ([3d4c662](https://github.com/devops-tashtiot/devops-api/commit/3d4c662160a7ab6824a9a1e7dce211e879063229))

## [0.2.3] - 2026-07-06

### Bug Fixes

- *(bitbucket,jira)* Correct user-directories endpoint path (was 404ing on user-dirs) ([3cc78ca](https://github.com/devops-tashtiot/devops-api/commit/3cc78ca48b8c8e1032400413d31e6800cbd57c86))

## [0.2.2] - 2026-07-06

### Bug Fixes

- *(api)* Hardcode https for argocd/sonarqube client URLs ([e8c74ad](https://github.com/devops-tashtiot/devops-api/commit/e8c74adeed9cd68dbe25ab061592986fc40da6b7))

## [0.2.1] - 2026-07-06

### Bug Fixes

- *(api)* Remove invalid ssh_port kwarg from Git() instantiation ([748e2ff](https://github.com/devops-tashtiot/devops-api/commit/748e2ffcc657074629abf3f3c0b73b5e9dcd6418))

### Miscellaneous Tasks

- Retrigger pipeline after transient tag-push race ([77b0967](https://github.com/devops-tashtiot/devops-api/commit/77b0967710c259a51319b9a77c3f0dcb2e2df2d3))

## [0.2.0] - 2026-07-06

### Features

- *(api)* Add ArgoCD, Artifactory, Bitbucket, Confluence, Jira, and SonarQube modules ([add84ae](https://github.com/devops-tashtiot/devops-api/commit/add84ae8920474028e136f3b3ceb0a0f6740e092))

## [0.1.1] - 2026-07-06

### Bug Fixes

- *(deps)* Pin tashtiot-apis-library to the published 0.1.0 release wheel ([de9e918](https://github.com/devops-tashtiot/devops-api/commit/de9e918c9c79f6c4d1393e07ea0bad9a9bf7e810))

## [0.1.0] - 2026-07-06


