This daemon listens for [GitLab Webhooks](https://docs.gitlab.com/ee/user/project/integrations/webhooks.html#webhooks) build events and downloads build artifacts to the specified directory.

Why it is **more secure than deploy by GitLab CI**? It is good to know that if you want to deploy by build script (`.gitlab-ci.yml`) this script needs to have access to your server (e.g. FTP password or SSH keys). If somebody with push permission change `.gitlab-ci.yml` to print this secret to build log he will be able to access your server and upload anything to any directory, even to the production (if you do Continuous Delivery).

# Usage

The daemon can be run standalone, but recommended is to use Docker image.

Example `docker-compose.yml`:

``` yaml
deployer:
  image: bobik/gitlab-ci-deployer
  restart: unless-stopped
  environment:
    VIRTUAL_HOST: ci-deployer.example.com  # for nginx-proxy
    BUILD_NAME: deploy # Only job named "deploy" will be deployed
    TARGET_DIR: /sites/{slug_project_name}-{build[commit][sha]}.ci.example.com
  env_file: secrets.env
  volumes:
    - static_sites:/sites
```

- `BUILD_NAME`: Deploy only job with this name.

- `TARGET_DIR`: Specifies where artifacts should be extracted. You can use this wildcards:

  - `unsafe_received_data`: Payload from webhook request. Can be planted by an attacker (if he steals your secret token).
  - `project`: [Project object](https://docs.gitlab.com/ee/api/projects.html#get-single-project) loaded from GitLab API.
  - `build`: [Job object](https://docs.gitlab.com/ee/api/jobs.html#get-a-single-job) loaded from GitLab API.
  - `slug_build_ref`: Slugified `build[ref]` (GIT branch)
  - `slug_project_name`: Slugified `project[name]`

Example `secrets.env`:

```
GITLAB_API_TOKEN=your-account-api-key
GITLAB_WEBHOOK_TOKENS=secret-very-long-random-generated-token,next-token,next-token
```

- `GITLAB_API_TOKEN` can be generated at [Profile → Access tokens](https://gitlab.com/profile/personal_access_tokens) for an account with access to projects you want to deploy. You can use multiple tokens for multiple accounts.

- `GITLAB_WEBHOOK_TOKENS` is "password" for your server. You should generate it randomly and use in Webhooks config of trusted projects.

# How to configure GitLab

GitLab project → Settings → Webhooks:

- URL: https://ci-deployer.example.com/deployer
- Build events
- Secret token
- Enable SSL verification

## Link to site in GitLab UI

GitLab supports showing links to deployed site [on multiple places](https://docs.gitlab.com/ee/ci/environments/#environment-url) in it's UI:

![Link to environment in merge request in GitLab](https://docs.gitlab.com/ce/ci/img/environments_mr_review_app.png)

You can configure it in `.gitlab-ci.yml` like this:

```yaml
deploy:
  environment:
    name: review/$CI_BUILD_REF_NAME
    url: http://$CI_BUILD_REF_NAME-$CI_BUILD_REF.ci.example.com
```

# Security warning

The deployer's HTTP server does not support HTTPS, so **you should use proxy with HTTPS termination** (like [nginx-proxy](https://github.com/jwilder/nginx-proxy)). **It is critical for security of your server and GitLab account to keep this tokens secret.** If you do not use HTTPS, your secret tokens will not be encrypted on the network what means attacker will be able to upload anything to your server and control your GitLab account. Also you should use **trusted SSL certificate** on the proxy to be protected against MITM attack (they can steal your tokens).

# How to test it locally

For development purposes you can run deployer like this:

```
docker run --name deployer --rm -v $(pwd)/deployer.py:/deployer.py -e "GITLAB_API_TOKEN=xxxx" -e "GITLAB_WEBHOOK_TOKENS=xxx" -e "TARGET_DIR=/sites/{slug_build_ref}-{slug_project_name}-ci.example.com" -e "BUILD_NAME=deploy" -e "DEBUG=1" -p 8080:8080 bobik/gitlab-ci-deployer
```

Then you can edit script by an editor and to apply changes just ctlr+C, arrow up, enter.

To mockup GitLab's webhook call use curl:

```
curl --request POST -H "X-Gitlab-Token: xxxx" --header "Content-Type: application/json" --data '{just paste here JSON payload your catched on a server (with DEBUG: 1)}' http://localhost:8080/deployer
```
