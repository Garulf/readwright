# mkreadme examples

Each directory is a self-contained fake project with a `readme.yaml`, a `README.md.j2` and the
`README.md` that `mkreadme render` produces from them. Run `mkreadme render` inside one to regenerate.

| Example | Shows |
| --- | --- |
| [kitchen-sink](kitchen-sink/) | Every general helper: logo/center header, badge presets + custom + donation badges with a global style, toc, screenshots with captions and dark/light variants, subdir gallery, `include_file`, `cli_help`, `snippet`, `details`, `callout`, `config_table`, `env_table`, `entry_points_table`, `columns`, `video`, `changelog`, `gh_link`, `related_repos`, `contributors`, `git_sha`/`git_tag`/`today`, `spdx_link`, an `unsplash()` hero image, a repo-local partial override |
| [config-only](config-only/) | No template at all: a fully annotated `readme.yaml` using every config key (including an Unsplash `banner:`), rendered by the packaged `base.md.j2`. Read it as the config reference |
| [minecraft-mod](minecraft-mod/) | Gradle/NeoForge detection, Unsplash `banner:`, `modrinth`/`curseforge` badges, `mc_versions()`, `mod_dependencies()` |
| [ha-card](ha-card/) | `hacs.json` detection, `unsplash()` from an image URL, `hacs`/`ha-version` badges, `my_ha_link()`, `code_block()` |
| [flow-plugin](flow-plugin/) | Flow Launcher `plugin.json` detection and the `pm install` snippet |

The kitchen sink uses `git_sha()` and `today()`, so its committed `README.md` will always be a little
behind; that is deliberate, to show why those helpers are a poor fit for `mkreadme check`.
