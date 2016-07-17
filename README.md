This daemon listens for [GitLab Webhooks](http://docs.gitlab.com/ce/web_hooks/web_hooks.html) build events and downloads build artifacts to the specified directory.

Why it is **secured than deploy by GitLab CI**? It is good to know that if you want to deploy by build script (`.gitlab-ci.yml`) this script needs to have access to your server (e.g. FTP password or SSH keys). If somebody with push permission change `.gitlab-ci.yml` to print this secret to build log he will be able to access your server and upload anything to any directory, even to the production (if you do Continuous Delivery).

# Usage

The daemon can be run standalone, but recommended is to use Docker image.

Example `docker-compose.yml`:

``` yaml
deployer:
  image: bobik/gitlab-ci-deployer
  restart: unless-stopped
  environment:
    VIRTUAL_HOST: ci-deployer.example.com  # for nginx-proxy
    TARGET_DIR: /sites/{slug_project_name}-{build[commit][short_id]}.ci.example.com
  env_file: secrets.env
  volumes:
    - static_sites:/sites
```

- `TARGET_DIR` variable specifies where artifacts should be extracted. You can use this wildcards:

  - `unsafe_received_data`: Payload from webhook request. Can be planted by an attacker (if he steals your secret token).
  - `project`: [Project object](http://docs.gitlab.com/ce/api/projects.html#get-single-project) loaded from GitLab API.
  - `build`: [Build object](http://docs.gitlab.com/ce/api/builds.html#get-a-single-build) loaded from GitLab API.
  - `slug_build_ref`: Slugified `build[ref]` (GIT branch)
  - `slug_project_name`: Slugified `project[name]`

Example `secrets.env`:

```
GITLAB_API_TOKEN=your-account-api-key
GITLAB_WEBHOOK_TOKENS=secret-very-long-random-generated-token,next-token,next-token
```

- GITLAB_API_TOKEN can be generated at [Profile → Access tokens](https://gitlab.com/profile/personal_access_tokens) for an account with access to projects you want to deploy. You can use multiple tokens for multiple accounts.

- GITLAB_WEBHOOK_TOKENS is "password" for your server. You should generate it randomly and use in Webhooks config of trusted projects.

# How to configure GitLab

GitLab project → Settings → Webhooks:

- URL: https://ci-deployer.example.com/deployer
- Build events
- Secret token
- Enable SSL verification

# Security warning

The deployer's HTTP server does not support HTTPS, so **you should use proxy with HTTPS termination** (like [nginx-proxy](https://github.com/jwilder/nginx-proxy)). **It is critical for security of your server and GitLab account to keep this tokens secret.** If you do not use HTTPS, your secret tokens will not be encrypted on the network what means attacker will be able to upload anything to your server and control your GitLab account. Also you should use **trusted SSL certificate** on the proxy to be protected against MITM attack (they can steal your tokens).
