# T Cat Auto Poster website

This repository contains the public information website for T Cat Auto Poster,
an independent creator tool for organizing user-owned video content and
preparing publishing actions.

## Current status

This repository is a static information website. It does not implement Login
Kit, OAuth, Content Posting API, `video.publish`, automated posting, or a TikTok
Production Review submission. TikTok Direct Post integration must be completed
and tested in Sandbox before review.

`CONTACT_EMAIL_REQUIRED` remains in the Privacy Policy and Terms of Service.
Replace every occurrence with a monitored public contact address before public
Production use or review submission. While it remains, the website is only
conditionally complete and Production Review submission is prohibited.

## Files

- `index.html`: public service description
- `privacy.html`: Privacy Policy
- `terms.html`: Terms of Service
- `styles.css`: shared responsive presentation
- `.nojekyll`: direct GitHub Pages static hosting
- `tests/validate-site.ps1`: local acceptance checks

## Local preview

From the repository root, run:

```powershell
python -m http.server 8000 --bind 127.0.0.1
```

Then open `http://127.0.0.1:8000/`. The expected local legal routes are
`http://127.0.0.1:8000/privacy.html` and
`http://127.0.0.1:8000/terms.html`.

Run the acceptance checks with:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\validate-site.ps1
```

## GitHub Pages

The intended Pages source is the `main` branch and `/root` folder. After the
repository owner and Pages URL are known, verify these HTTPS routes directly:

- website root
- `/privacy.html`
- `/terms.html`
- `/styles.css`

Do not report public completion until all four return HTTP 200 and navigation
between the pages has been checked on the deployed site.

## TikTok URL Properties verification

TikTok for Developers may provide a signature file for URL Properties
ownership verification. Download that file from the Developer Portal and:

1. Keep its exact filename and contents unchanged.
2. Place the signature file at this repository root beside `index.html`.
3. Commit and push it to the Pages source branch.
4. Open its exact public HTTPS URL and require HTTP 200.
5. Only then initiate ownership verification in the Developer Portal.

No guessed signature file is included in this repository.

## Planned Desktop Login Kit settings

Planned redirect URI:

```text
http://127.0.0.1:3455/callback/
```

Register the redirect URI as a static absolute URI with its loopback host and
explicit port. Do not append query parameters or a fragment. The future OAuth
implementation must use PKCE and an unpredictable `state` value with callback
validation. Client secrets and refresh tokens must remain in a secure local or
server-side store. Access tokens must never be committed and must be refreshed
through the supported token lifecycle.

## Secret handling

Never commit a TikTok client secret, access token, refresh token, TikTok
password, GitHub personal access token, private key, or `.env` file. This site
is completely public once hosted with GitHub Pages, including its source.

## Remaining integration work

The following work is outside this website repository and remains incomplete:

- Login Kit and OAuth callback service
- PKCE, `state` validation, secure token storage, and refresh flow
- Content Posting API and approved `video.publish` scope
- creator information and privacy-option UI
- explicit final publishing consent flow
- Sandbox OAuth and SELF_ONLY posting tests
- end-to-end review demo video
- Production Review configuration and submission

Do not submit TikTok Production Review from this website task.
