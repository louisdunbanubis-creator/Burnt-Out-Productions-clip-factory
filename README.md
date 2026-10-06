# Burnt-Out-Productions Clip Factory

A $0, iPhone-first content clipping and production pipeline.

## Clip Maker

The **Open Clip Maker** dashboard button launches the GitHub Actions clip maker directly from an iPhone.

The automatic workflow now:
1. Accepts an authorized/licensed source URL.
2. Downloads the source on a free GitHub-hosted runner.
3. Extracts and transcribes the **entire video** with Whisper.
4. Scores transcript moments against the selected niche plus high-interest language and speech density.
5. Selects the strongest non-overlapping moments.
6. Converts each moment to 9:16.
7. Burns in captions using the consistent Redthaproducer-style display font.
8. Stitches the best moments together into one finished montage.
9. Uploads the MP4 and analysis metadata as an artifact for iPhone review.

The project remains multi-niche: cars/JDM, construction, podcasts, sports, and interesting/engineering.

## Brand typography

The production text treatment uses **Anton**, an open-license condensed display font, as the consistent substitute for the Redthaproducer closing-credit look. It is used for hooks and burned-in captions so the machine has one recognizable text identity. The exact original closing-credit typeface can be swapped in later without changing the renderer.

Anton is distributed under the SIL Open Font License. [Anton source and license metadata](https://github.com/google/fonts/blob/main/ofl/anton/METADATA.pb)

## Rights gate

Only process footage you own, have permission/license to use, public-domain material, applicable Creative Commons material, or footage you are using in a lawful transformative/commentary workflow.

A source being publicly viewable does not automatically grant reuse rights.

## Free-cloud architecture

Heavy work runs in GitHub Actions; the iPhone is the control and review device. Public repositories can use standard GitHub-hosted runners without runner-minute charges. [GitHub Actions billing documentation](https://docs.github.com/en/actions/concepts/billing-and-usage)

The dashboard is designed to deploy as a static Cloudflare Pages site, so the phone UI does not require a paid server. Cloudflare's Git integration can automatically redeploy the site whenever this repository changes. [Cloudflare Pages Git integration](https://developers.cloudflare.com/pages/configuration/git-integration/)
