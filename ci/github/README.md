# github-ci

How to deploy CI on Github:
1. Setup Webhook server
   Deploy the Django app that under ci/github/webhook-server/ as https://ikt.bj.intel.com/github-listener/
2. Create a Webhook on Github
   - Payload URL: <webhook-proxy-url>+https://ikt.bj.intel.com/github-listener/
       e.g.: https://github-webhooks-intel-prod.azurefd.net/sandbox/messages?ci=https://ikt.bj.intel.com/github-listener/
   - Content type: application/json
   - SSL verification: enabled
   - Events: push, pull_request
3. Create Jenkins pipeline jobs by the following jenkinsfiles:
   - github-ci-kernel-lts-staging: ci/github/kernel-lts-staging/githubci.jf
   - github-ci-kernel-staging: ci/github/kernel-staging/githubci.jf
4. Add nodes for CI jobs
   - Set label: githubci
   - Register the prefix of node name in githubci.jf: NODE_SITE_MAP if necessary
   - Set 4 executors for each CI node(make sure the number of cpus > 65(15 * 4 + 5))

References:
1. https://1source.intel.com/docs/faq/ci_and_webhooks

Current CI enabled projects are:
1. kernel-lts-staging
2. kernel-staging(WorkingInProgress)


