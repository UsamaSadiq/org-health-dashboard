## Contributor License Agreement (CLA)

This project requires contributors to sign a Contributor License Agreement (CLA) before their contributions can be accepted. This ensures that all contributions are made under the AGPL-3.0-or-later license and that we have the necessary permissions to use and distribute the contributions.

### Process

1. When you open a pull request, the cla-assistant bot will automatically check if you've signed the CLA.
2. If not, the PR will be blocked until the CLA is signed.
3. For trivial contributions (documentation fixes, typos), we provide a DCO fast path (see below).

### DCO Fast Path for Trivial Contributions

For trivial contributions that meet all of these criteria:
- Less than 20 lines changed
- Only documentation, comments, or whitespace changes
- No new functionality added

Contributors can instead sign an
[individual DCO](https://developercertificate.org/) with the following text:

> I certify that this contribution does not contain any contributions from third parties and that I have the legal rights to make this contribution on my own behalf.


This follows the OpenStack precedent from July 2025.


### How to Sign the CLA

Sign the CLA via the cla-assistant bot interface when your PR is blocked. You'll receive a link to the signing interface automatically.

For maintainers: CLA compliance is enforced via [cla-assistant](https://cla-assistant.io/) with the configuration in `.github/workflows/cla-assistant.yml`.