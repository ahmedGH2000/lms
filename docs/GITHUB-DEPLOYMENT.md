# Automatic deployment to learn.barmejly.ly

This deployment is specific to `github.com/ahmedGH2000/lms` and the existing
Nightjar production stack at `/opt/nightjar-learning`. A push to `main` tests
the project, builds an immutable container, backs up the live site, deploys only
the `nightjar-learning` Compose project, and checks the local application on
port 8088. Other Docker projects are not referenced.

## One-time setup before the first automated push

On the CachyOS computer, inside the new project folder, create a dedicated key:

```bash
ssh-keygen -t ed25519 -f "$HOME/.ssh/nightjar_github_deploy" -C "github-nightjar-deploy"
```

Copy the two setup files and public key to the VPS:

```bash
scp deploy/production/nightjar-deploy \
  deploy/production/nightjar-ssh-entry \
  deploy/production/install-ci-deployer.sh \
  "$HOME/.ssh/nightjar_github_deploy.pub" \
  b3b3@102.203.200.40:/home/b3b3/
```

Connect to the VPS and install the restricted deployment account:

```bash
ssh b3b3@102.203.200.40
sudo bash /home/b3b3/install-ci-deployer.sh \
  /home/b3b3/nightjar_github_deploy.pub
sudo ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
sudo sed 's/^/102.203.200.40 /' /etc/ssh/ssh_host_ed25519_key.pub
```

The last command prints the exact known-hosts line. It is public host identity,
not a password.

Test the dedicated key from CachyOS:

```bash
ssh -i "$HOME/.ssh/nightjar_github_deploy" \
  -o IdentitiesOnly=yes nightjar-deploy@102.203.200.40 nightjar-probe
```

In GitHub, open **Settings → Environments → New environment** and create
`production`. Limit deployment branches to `main`, then add these environment
secrets:

- `VPS_HOST`: `102.203.200.40`
- `VPS_USER`: `nightjar-deploy`
- `VPS_SSH_PRIVATE_KEY`: the complete output of
  `cat "$HOME/.ssh/nightjar_github_deploy"`
- `VPS_KNOWN_HOSTS`: the complete known-hosts line printed on the VPS

Do not put the VPS password, Nightjar `.env`, database password, administrator
password, or video secret in GitHub.

## First test

Push the new project to `main`. Open the repository's **Actions** tab and watch
**Test, build and deploy Nightjar**. A successful run leaves the site at
`https://learn.barmejly.ly` and records the deployed commit under
`/opt/nightjar-learning/current`.

On the VPS, inspect the result without exposing secrets:

```bash
sudo docker ps --filter name=nightjar-learning \
  --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}'
sudo readlink -f /opt/nightjar-learning/current
sudo find /opt/nightjar-learning/deployment-backups -mindepth 1 -maxdepth 1 \
  -type d -printf '%f\n' | sort
```

The deployer retains old images, source releases, and exported backups. Cleanup
is intentionally manual. The private video directory remains mounted at
`/opt/nightjar-learning/data/private-media` and is never copied or deleted by
deployment.
