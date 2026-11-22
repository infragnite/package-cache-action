# package-cache-action

Sends a GitHub Actions job's downloads through the Infragnite package cache
(`https://maven.infragnite.dev`). The cache keeps every file it fetched from Maven Central, the
Gradle Plugin Portal, Gradle distributions and GitHub releases, and keeps serving them when an
upstream rate-limits or is down.

The action swaps the job's GitHub OIDC token for a cache token (valid 6 hours). Only repositories
on the cache's trust list get one; for any other the action fails.

```yaml
permissions:
  contents: read
  id-token: write

steps:
  - uses: actions/checkout@v4
  - uses: infragnite/package-cache-action@<commit sha>   # pin by full commit SHA
    # with:
    #   maven: 'true'   # also Maven (writes ~/.m2/settings.xml)
  - run: ./gradlew build
```

Inputs:
- `url`: the cache, default `https://maven.infragnite.dev`.
- `gradle` (default `true`): installs an init script that sends Maven Central and Plugin Portal
  repositories to the cache.
- `maven` (default `false`): writes `~/.m2/settings.xml` with the cache as Central's mirror.

Outputs `token`, and sets `PACKAGE_CACHE_URL` and `PACKAGE_CACHE_TOKEN` for other downloads:
`curl -u ci:$PACKAGE_CACHE_TOKEN $PACKAGE_CACHE_URL/gradle-dist/gradle-8.10.2-bin.zip`, or
`$PACKAGE_CACHE_URL/github/<owner>/<repo>/releases/download/<tag>/<file>`.
