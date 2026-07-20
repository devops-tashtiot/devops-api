# Changelog

All notable changes to this project will be documented in this file.

## [0.3.4] - 2026-07-20

### Bug Fixes

- *(jira)* Validate admin_user/admin_group exist before create; remove dead chat/dns/haproxy modules ([ee73d20](https://github.com/devops-tashtiot/devops-api/commit/ee73d20fb14f3f4a2b63f29654bfe4881436e6d5))

## [0.3.3] - 2026-07-20

### Testing

- *(bitbucket)* Cover public field pass-through, schema boundaries, and permission idempotency ([6fe5bc7](https://github.com/devops-tashtiot/devops-api/commit/6fe5bc7a9b7e4a1df24374a933583139d60ee613))

## [0.3.2] - 2026-07-20

### Bug Fixes

- *(bitbucket)* Implement missing admin pre-check, fix silent-failure rollback path ([cf13c2b](https://github.com/devops-tashtiot/devops-api/commit/cf13c2b4d4fa1ad4885174d8beba28c44b70c830))

## [0.3.1] - 2026-07-20

### Bug Fixes

- *(bitbucket)* Two test bugs found running the suite live against the real cluster ([d3cde1c](https://github.com/devops-tashtiot/devops-api/commit/d3cde1c143c31f84dca6bd9b1c7d7d91592269ed))

## [0.3.0] - 2026-07-19

### Bug Fixes

- *(bitbucket)* Sync is unsupported by Bitbucket, return 501 not a fake success ([d14e2bd](https://github.com/devops-tashtiot/devops-api/commit/d14e2bd1f5b5c43459a56dd9357ec3d18f8ad7fd))
- *(confluence)* Sync is unsupported by Confluence, return 501 ([3a22e61](https://github.com/devops-tashtiot/devops-api/commit/3a22e61380fc327c6c1b1ff4026e9806b94b0fe3))
- *(confluence)* Delete_space must poll until actually gone ([f10eec6](https://github.com/devops-tashtiot/devops-api/commit/f10eec6af984d50ce52ed08631da4e6523e0b1f9))
- *(confluence)* Install_plugin must poll until UPM install actually finishes ([c4823a0](https://github.com/devops-tashtiot/devops-api/commit/c4823a0cfe8733cb2c97e1c261349d9ff29c2f06))
- *(confluence)* Follow redirects when polling plugin install task ([01dbc7d](https://github.com/devops-tashtiot/devops-api/commit/01dbc7de2579f692cc8ee797cd700b1629e6ed31))
- *(bitbucket)* Delete project's repos before deleting the project ([d0c7f90](https://github.com/devops-tashtiot/devops-api/commit/d0c7f90cb1034a0457add5b6db1df8048a9e03fc))
- *(jira)* Require admin_user — Jira always mandates a project lead ([52661cd](https://github.com/devops-tashtiot/devops-api/commit/52661cd24535f6dceb9d3353fe0036905555778c))
- *(jira)* Sync is unsupported by Jira, return 501 not a false attempt ([e82c9ae](https://github.com/devops-tashtiot/devops-api/commit/e82c9ae45ebc23e331c0e9828e1bfd96aa46d45c))
- *(sonarqube)* DELETE /consumer/{name} was shadowed by group-delete route ([a4f4872](https://github.com/devops-tashtiot/devops-api/commit/a4f487286158a7bd6b73c28e5e87872c503d7262))
- *(docker)* Install openssh-client so the Git connector's SSH clone works ([01ffda6](https://github.com/devops-tashtiot/devops-api/commit/01ffda6d5c85b0ae1305ec8c7f5d435726619aa4))
- *(argocd)* Entire test suite was never collectible (wrong config object) ([d83f4a3](https://github.com/devops-tashtiot/devops-api/commit/d83f4a33ac9639bc92aa2315b4113e88b52cc25b))
- *(argocd)* Remove unused ARGOCD_SCHEME/ARGOCD_PORT config fields ([bf9f50c](https://github.com/devops-tashtiot/devops-api/commit/bf9f50c5ba7549a7a8935182f026c876c320f8aa))
- *(argocd,docker)* Install kubectl in the image; document live-check findings ([f833a53](https://github.com/devops-tashtiot/devops-api/commit/f833a53cbb3924c998b3e4b324bf83611f4bb740))
- *(argocd,docker)* Token-based ArgoCD auth (from_credentials didn't exist); trust Cloudflare Origin CA ([6441773](https://github.com/devops-tashtiot/devops-api/commit/6441773678bf128cba3d9715b06352356aa4f0f8))
- *(sonarqube,global-conf)* Remove unused config fields ([968ece8](https://github.com/devops-tashtiot/devops-api/commit/968ece8a76edce4bd8a0c2c4ca0fb30252347906))
- *(sonarqube)* PUT /consumer/{name} called git.update_file, which doesn't exist ([be0c840](https://github.com/devops-tashtiot/devops-api/commit/be0c840559719ba6979a15ce5a253cb46dde8422))
- *(bitbucket)* E2e test's ADMIN_USER default was a nonexistent user, not "admin" ([0371a66](https://github.com/devops-tashtiot/devops-api/commit/0371a66c8c23f5a3b3b965ab4da099bf8d0b5bec))
- *(sonarqube)* Group e2e test sent a flat body, route needs metadata+spec ([9f37b17](https://github.com/devops-tashtiot/devops-api/commit/9f37b17ffcfdb782d69c36d9a26fd40cfac57843))
- *(argocd,jira,bitbucket,sonarqube)* Drop dead e2e token-minting now that AUTH_ENABLED is off ([c7a0c33](https://github.com/devops-tashtiot/devops-api/commit/c7a0c3300ed57ebbd51925c18f3e208ea7800539))
- *(argocd)* Wait for cluster-secret app visibility before syncing ([0860264](https://github.com/devops-tashtiot/devops-api/commit/0860264e0d1d08e7f6065133dbdb5a117d2562c3))

### CI/CD

- Also trigger the build+deploy pipeline on push to check-api ([b80a06b](https://github.com/devops-tashtiot/devops-api/commit/b80a06bda24e025484b2ef29264213ed09ddb698))
- Trigger build+deploy pipeline on push to any branch ([42e7aa7](https://github.com/devops-tashtiot/devops-api/commit/42e7aa7109052c365a0dff4912ab6e68d472e7bc))
- Give non-master branches a SHA-based tag instead of git-cliff semver ([0357324](https://github.com/devops-tashtiot/devops-api/commit/03573240ec74e9065d554ec3efb7aa149c79570a))

### Documentation

- Add cluster-verification playbook for checking devtool APIs live ([73bf192](https://github.com/devops-tashtiot/devops-api/commit/73bf192ef15a8bfbaeeb5f87ba4367d5ad7df221))
- *(sonarqube)* Document remaining live blockers on consumer-config routes ([43dd31f](https://github.com/devops-tashtiot/devops-api/commit/43dd31f695dc77941996c467740041fb93c77276))
- *(argocd)* Document that create_cluster_secret cannot work at all ([045ef91](https://github.com/devops-tashtiot/devops-api/commit/045ef91b4f1ccd9bf80e8e3d221b81253a2f03f8))
- *(argocd)* Note the create_app gap may be fixed by a future apis-library bump ([1f9444a](https://github.com/devops-tashtiot/devops-api/commit/1f9444abe3758b400e9c12907616fba061ae9992))
- *(argocd)* Note the DELETE hostname-parsing fix already exists upstream, just not in the pinned version ([b2be4fb](https://github.com/devops-tashtiot/devops-api/commit/b2be4fba634e9f920ace6f61bc59bf9c24a705de))
- *(argocd)* Correct v1.1.2 re-check — neither known gap is actually fixed ([e5b2755](https://github.com/devops-tashtiot/devops-api/commit/e5b27550a29d1f44d1a7abbc35abb92cf72a0679))
- Record live end-to-end auth verification and two real gotchas found ([6e071f9](https://github.com/devops-tashtiot/devops-api/commit/6e071f967d2e1a61195f32fc17eadde7da7afc15))
- Root-cause the DELETE timeout — wrong SSH port, unreachable anyway ([7d48523](https://github.com/devops-tashtiot/devops-api/commit/7d48523c93d04a3c3da43ae4ba673a15ab2ed22a))
- Record SSH key mount as the final piece for the DELETE bugs ([e26f469](https://github.com/devops-tashtiot/devops-api/commit/e26f469b4aa993303b94e32ff7aeb2ee92b765f8))
- DELETE /{env}/{name} and DELETE /consumer/{name} confirmed fixed live ([716ba27](https://github.com/devops-tashtiot/devops-api/commit/716ba2789c36c0f9ffc80028ec6ea7b757aeb797))
- *(sonarqube)* Root-cause PUT /consumer/{name} 406 to an apis-library bug, open upstream fix ([340f83f](https://github.com/devops-tashtiot/devops-api/commit/340f83f848a31be85e4216cc6b93a3628469bc45))

### Features

- *(auth)* Enable inbound JWT auth via tashtiot-apis-library ([1f0b96a](https://github.com/devops-tashtiot/devops-api/commit/1f0b96a13688c597d97b3c76bcfaaf7f2a12cec5))
- *(argocd)* Authenticate outbound ArgoCD calls via SSO instead of a caller-supplied token ([e2c25b3](https://github.com/devops-tashtiot/devops-api/commit/e2c25b36ec998db3321d85b4b886fdef13cc2120))
- Bump tashtiot-apis-library to v1.2.1 ([92498c5](https://github.com/devops-tashtiot/devops-api/commit/92498c5ffc878bc8ae2b49c024451f72a3a7ddad))

### Miscellaneous Tasks

- *(deps)* Bump tashtiot-apis-library to v1.1.2 ([06f4022](https://github.com/devops-tashtiot/devops-api/commit/06f40222f01252193460bea9a2afdc937b41f011))

### Other

- *(confluence)* Drop POST /space-import/upload, unnecessary ([8e67f4c](https://github.com/devops-tashtiot/devops-api/commit/8e67f4c4960080833475d178e336e76f22a2a497))

### Refactor

- *(confluence)* Extract shared upload_to_s3 helper; disable user-directories endpoints ([050c306](https://github.com/devops-tashtiot/devops-api/commit/050c306b6afcf281eafc6e3b0ce432995e0e9643))

### Testing

- *(bitbucket)* Rename e2e file, add admin_group and repo-cascade coverage ([d663d75](https://github.com/devops-tashtiot/devops-api/commit/d663d75adf4c91575f4bf3c6a5e5e01615d0ab0c))
- *(jira)* Add real e2e test suite ([3d8295b](https://github.com/devops-tashtiot/devops-api/commit/3d8295bf803e1addb5f299c978179ca0fb7bcc08))
- *(e2e)* Send a Bearer token now that inbound auth is enabled ([2064440](https://github.com/devops-tashtiot/devops-api/commit/2064440077ff4ffc3194354b51d7dbc37e87012a))

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


